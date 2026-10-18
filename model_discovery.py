"""Operator-run model discovery.

Discovery is *not* approval: this module writes ``config/discovered_models.json``
with ``approval_status: discovered`` so models are visible for review but never
routable. An administrator promotes a model by copying it into
``config/model_registry.json`` with pricing, capabilities, and
``approval_status: approved``.

Run periodically (or from an admin job), never on the request path:

    python -m model_discovery
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_DISCOVERED_PATH = ROOT / "config" / "discovered_models.json"
_TIMEOUT = float(os.getenv("AI_MODEL_DISCOVERY_TIMEOUT_SECONDS", "10"))


async def _resolve_json(response: Any) -> Any:
    import inspect

    if isinstance(response, Mapping):
        return response
    data = getattr(response, "json", response)
    data = data() if callable(data) else data
    if inspect.isawaitable(data):
        data = await data
    return data


def _models_url(provider: Any) -> str:
    base = provider.base_url
    if provider.base_url_env:
        base = os.getenv(provider.base_url_env, "") or base
    base = os.path.expandvars(base or "").rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return f"{base}/models" if base else ""


def _active(provider: Any, values: Mapping[str, str]) -> bool:
    if not provider.enabled:
        return False
    if provider.enabled_env:
        return str(values.get(provider.enabled_env, "")).strip().lower() in {"1", "true", "yes", "on"}
    return True


def _per_million(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    # OpenRouter publishes token prices in dollars-per-token. Most provider
    # feeds publish dollars-per-million-token. Values below $0.01/token are
    # unambiguously token-denominated; a legitimate $0.005/M token price would
    # otherwise be off by six orders of magnitude.
    return number * 1_000_000 if 0 < number < 0.01 else number


def _openai_model_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    input_cost = _per_million(pricing.get("prompt", pricing.get("input")))
    output_cost = _per_million(pricing.get("completion", pricing.get("output")))
    architecture = row.get("architecture") if isinstance(row.get("architecture"), Mapping) else {}
    input_modalities = {str(item).lower() for item in architecture.get("input_modalities", [])}
    capabilities = ["text"]
    if "image" in input_modalities:
        capabilities.append("vision")
    if bool(row.get("supports_tools", row.get("tool_choice", False))):
        capabilities.append("tool_calling")
    top_provider = row.get("top_provider") if isinstance(row.get("top_provider"), Mapping) else {}
    metadata: Dict[str, Any] = {
        "capabilities": capabilities,
        "context_window": int(
            row.get("context_length")
            or top_provider.get("context_length")
            or 128_000
        ),
        "max_output_tokens": int(
            top_provider.get("max_completion_tokens")
            or row.get("max_output_tokens")
            or 8_192
        ),
    }
    if input_cost is not None and output_cost is not None:
        metadata.update({
            "input_cost_per_million": input_cost,
            "output_cost_per_million": output_cost,
            "pricing_source": "provider_feed",
        })
    return metadata


async def discover_openai_compatible(
    provider: Any, api_key: str, client: Any
) -> List[Dict[str, Any]]:
    url = _models_url(provider)
    if not url:
        return []
    response = await _call(client, "get", url, headers={"Authorization": f"Bearer {api_key}"})
    payload = await _resolve_json(response)
    rows = (payload or {}).get("data") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return []
    return [
        {
            "id": str(row.get("id")),
            "upstream_model": str(row.get("id")),
            **_openai_model_metadata(row),
        }
        for row in rows
        if isinstance(row, Mapping) and row.get("id")
    ]


def _deployment_names(value: str) -> List[str]:
    names = [item.strip() for item in str(value or "").split(",") if item.strip()]
    if not names:
        return []
    parsed: List[str] = []
    for item in names:
        if item.startswith("["):
            try:
                rows = json.loads(item)
            except ValueError:
                rows = []
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, Mapping):
                    name = row.get("deployment") or row.get("name") or row.get("model")
                else:
                    name = row
                if str(name or "").strip():
                    parsed.append(str(name).strip())
        else:
            parsed.append(item)
    return parsed


async def discover_azure_deployments(provider: Any, values: Mapping[str, str]) -> List[Dict[str, Any]]:
    names = _deployment_names(values.get("AZURE_OPENAI_DEPLOYMENTS", ""))
    return [
        {
            "id": name,
            "upstream_model": name,
            "capabilities": ["text"],
            "context_window": 128_000,
            "max_output_tokens": 8_192,
        }
        for name in names
    ]


async def discover_gemini(
    provider: Any, api_key: str, client: Any, values: Mapping[str, str]
) -> List[Dict[str, Any]]:
    base = values.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    response = await _call(
        client,
        "get",
        f"{base}/models",
        params={"key": api_key},
    )
    payload = await _resolve_json(response)
    rows = (payload or {}).get("models") if isinstance(payload, Mapping) else None
    output = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").removeprefix("models/")
        if not name:
            continue
        methods = {str(item) for item in row.get("supportedGenerationMethods", [])}
        output.append({
            "id": name,
            "upstream_model": name,
            "capabilities": ["text", "embedding"] if "embedContent" in methods else ["text"],
            "context_window": int(row.get("inputTokenLimit") or 128_000),
            "max_output_tokens": int(row.get("outputTokenLimit") or 8_192),
        })
    return output


async def discover_vertex(
    provider: Any, api_key: str, client: Any, values: Mapping[str, str]
) -> List[Dict[str, Any]]:
    names = _deployment_names(values.get("GOOGLE_VERTEX_MODELS", ""))
    if names:
        return [
            {
                "id": name,
                "upstream_model": name,
                "capabilities": ["text"],
                "context_window": 128_000,
                "max_output_tokens": 8_192,
            }
            for name in names
        ]
    project = values.get("GOOGLE_CLOUD_PROJECT", "").strip()
    region = values.get("GOOGLE_VERTEX_REGION", "").strip() or "global"
    if not project:
        return []
    url = (
        f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{region}/publishers/google/models"
    )
    response = await _call(client, "get", url, headers={"Authorization": f"Bearer {api_key}"})
    payload = await _resolve_json(response)
    rows = (payload or {}).get("models") if isinstance(payload, Mapping) else None
    output = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").rsplit("/", 1)[-1]
        if name:
            output.append({
                "id": name,
                "upstream_model": name,
                "capabilities": ["text"],
                "context_window": int(row.get("inputTokenLimit") or 128_000),
                "max_output_tokens": int(row.get("outputTokenLimit") or 8_192),
            })
    return output


async def discover_bedrock(provider: Any, client: Any) -> List[Dict[str, Any]]:
    response = await _call(client, "list_foundation_models")
    payload = await _resolve_json(response)
    rows = (payload or {}).get("modelSummaries") if isinstance(payload, Mapping) else None
    discovered = []
    for row in rows or []:
        model_id = row.get("modelId")
        if not model_id:
            continue
        discovered.append({
            "id": str(model_id),
            "upstream_model": str(model_id),
            "provider": "bedrock",
            "input_modalities": list(row.get("inputModalities") or []),
            "output_modalities": list(row.get("outputModalities") or []),
            "streaming": bool(row.get("responseStreamingSupported")),
        })
    return discovered


async def _call(client: Any, method: str, *args: Any, **kwargs: Any) -> Any:
    import inspect

    result = getattr(client, method)(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


async def _http_client() -> Any:
    import httpx

    return httpx.AsyncClient(timeout=_TIMEOUT)


async def discover(
    registry: Any = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    clients: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a discovered-models document. Never raises on a single provider."""
    from model_registry import ModelRegistry

    values = env or os.environ
    registry = registry or ModelRegistry()
    clients = clients or {}
    models: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    now = datetime.now(timezone.utc).isoformat()

    for provider in registry.providers.values():
        if not _active(provider, values):
            continue
        try:
            if provider.adapter == "bedrock_converse":
                client = clients.get(provider.id) or clients.get("bedrock")
                if client is None:
                    client = _boto_client(provider)
                rows = await discover_bedrock(provider, client)
            elif provider.id == "azure_openai":
                rows = await discover_azure_deployments(provider, values)
            elif provider.id == "google_vertex":
                key_envs = list(provider.api_key_envs) or [provider.api_key_env]
                api_key = next((values.get(name, "") for name in key_envs if values.get(name)), "")
                if not api_key:
                    continue
                client = clients.get(provider.id)
                created = client is None
                client = client or await _http_client()
                try:
                    rows = await discover_vertex(provider, api_key, client, values)
                finally:
                    if created and hasattr(client, "aclose"):
                        await _call(client, "aclose")
            elif provider.adapter == "gemini_generate":
                key_envs = list(provider.api_key_envs) or [provider.api_key_env]
                api_key = next((values.get(name, "") for name in key_envs if values.get(name)), "")
                if not api_key:
                    continue
                client = clients.get(provider.id)
                created = client is None
                client = client or await _http_client()
                try:
                    rows = await discover_gemini(provider, api_key, client, values)
                finally:
                    if created and hasattr(client, "aclose"):
                        await _call(client, "aclose")
            elif provider.adapter in {"openai_compatible", "openai_responses"}:
                key_envs = list(provider.api_key_envs) or [provider.api_key_env]
                api_key = next((values.get(name, "") for name in key_envs if values.get(name)), "")
                if not api_key:
                    continue
                client = clients.get(provider.id)
                created = client is None
                client = client or await _http_client()
                try:
                    rows = await discover_openai_compatible(provider, api_key, client)
                finally:
                    if created and hasattr(client, "aclose"):
                        await _call(client, "aclose")
            else:
                continue
        except Exception as exc:  # noqa: BLE001 - discovery must never break on one provider
            errors.append({"provider": provider.id, "error": str(exc)[:300]})
            continue
        for row in rows:
            models.append({
                "id": row["id"],
                "provider": provider.id,
                "upstream_model": row.get("upstream_model") or row["id"],
                "approval_status": "discovered",
                "discovered_at": now,
                **{
                    k: v for k, v in row.items()
                    if k not in {"id", "upstream_model", "provider", "approval_status", "discovered_at"}
                },
            })

    return {
        "schema_version": 1,
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d.%H%M"),
        "updated_at": now,
        "owner": "platform-routing",
        "discovered_models": models,
        "errors": errors,
    }


def _boto_client(provider: Any) -> Any:
    import boto3

    region = (os.getenv(provider.region_env, "") if provider.region_env else "") or provider.region or "us-east-1"
    return boto3.client("bedrock", region_name=region)


def write_discovered(document: Mapping[str, Any], path: Path = DEFAULT_DISCOVERED_PATH) -> Path:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


async def main() -> None:
    document = await discover()
    path = write_discovered(document)
    print(f"discovered {len(document['discovered_models'])} models -> {path}")
    for error in document["errors"]:
        print(f"  error: {error['provider']}: {error['error']}")


if __name__ == "__main__":
    asyncio.run(main())
