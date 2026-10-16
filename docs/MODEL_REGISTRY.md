# Model Registry (schema v2)

The model registry (`config/model_registry.json`) and task policy registry
(`config/task_policies.json`) are operational execution metadata. They never
contain customer prices, plans, credits, subscriptions, or paywalls.

Two principles govern every field:

1. **Declared, never inferred.** Provider identity, authentication mode,
   billing class, and approval are explicit. Nothing is guessed from an API key
   prefix, a model name, or a provider name.
2. **Discovery is not approval.** A model that has merely been discovered is
   inert until an administrator approves it.

## Provider fields

| Field | Meaning |
| --- | --- |
| `id` | Stable provider id used by routing, grants, and telemetry. |
| `adapter` | Wire protocol: `openai_responses`, `openai_compatible`, `anthropic_messages`, `gemini_generate`, `cohere_embed`, `bedrock_converse`, `bedrock_bearer`. |
| `api_key_env` / `api_key_envs` | Environment variables carrying static keys. Empty for SigV4 providers. |
| `auth` | Explicit auth mode: `bearer`, `anthropic`, `query`, `azure`, `sigv4`, `bedrock_bearer`, `none`. Defaults from the adapter when omitted. |
| `base_url` / `base_url_env` | Endpoint; `${VAR}` is expanded from the environment. |
| `enabled` / `enabled_env` | Static enablement plus an optional opt-in flag (e.g. `BEDROCK_ENABLED`). |
| `region` / `region_env` | AWS/Bedrock region. |

### Authentication is declared

`provider.resolved_auth` returns the declared `auth`, or the adapter default
(`bedrock_converse` → `sigv4`, `anthropic_messages` → `anthropic`, etc.). The
adapters and the readiness probe both read the same declaration, so they cannot
disagree. SigV4 providers carry no static key (`requires_api_key == false`) and
resolve credentials from the AWS chain (env keys, shared profile, or IAM task
role).

### Credential format is provider-verified

Each provider verifies credentials with its own wire format; the registry
declares which one, and the adapter, the readiness probe, and the tests all use
that single declaration. Nothing is sniffed from the key.

| Provider | `auth` | How the credential is sent | Verified by |
| --- | --- | --- | --- |
| OpenAI, OpenRouter, Moonshot, Mistral | `bearer` | `Authorization: Bearer <key>` | adapter + `/models` probe |
| Anthropic | `anthropic` | `x-api-key: <key>` + `anthropic-version` | adapter + `/v1/models` probe |
| Google Gemini (`google`) | `query` | `?key=<key>` query parameter | adapter + `/v1beta/models` probe |
| Google Vertex (`google_vertex`) | `bearer` | `Authorization: Bearer <access-token>` | adapter + probe |
| Azure OpenAI (`azure_openai`) | `azure` | `api-key: <key>` header (no `Authorization`); deployment URL keeps `?api-version=` | adapter + resource-level probe |
| Amazon Bedrock (`bedrock`) | `sigv4` | AWS SigV4 credential chain; no static key | credential-chain report |
| Bedrock gateway (`bedrock_bearer`) | `bedrock_bearer` | `Authorization: Bearer <key>` | adapter + probe |

Azure requests preserve the deployment path and its `?api-version=` query
rather than appending a second `/chat/completions` segment. The Azure probe
targets the resource-level `/openai/models?api-version=...` endpoint. Google
Gemini keys ride in the query string; Vertex uses a refreshed OAuth access
token as a bearer credential. Bedrock SigV4 resolves keys from
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, a shared profile, or an IAM/task
role, so readiness checks the chain (and an opt-in live probe) instead of a
static key.

## Model fields

Required (v1): `id`, `provider`, `upstream_model`, `enabled`, `user_selectable`,
`quality_tier`, `quality_score`, `latency_score`, `context_window`,
`max_output_tokens`, `capabilities`.

Schema v2 additions (all optional, safe defaults):

| Field | Default | Meaning |
| --- | --- | --- |
| `billing_class` | derived | `free`, `paid`, or `metered`. Derived as `free` only when both input and output prices are exactly `0.0`; otherwise `paid`. A `free` model with a non-zero price is rejected. |
| `approval_status` | `approved` | `approved`, `discovered`, or `disabled`. `enabled` is derived from it, so the two can never diverge. |
| `supported_regions` | `()` | Regions the model may serve in; empty means unrestricted. |
| `data_handling` | `""` | e.g. `no_training`, `retention_bounded`. |
| `health_status` | `unknown` | Operational hint, refined by the circuit breaker. |
| `pricing_version` | registry version | Recorded on every billed request. |
| `streaming`, `tool_calling`, `structured_output`, `vision` | from `capabilities` | Explicit booleans. Declaring one `true` without the matching capability is rejected. |

### Billing class is per model, not per provider

OpenRouter serves both free and paid models; Bedrock Claude is paid while an
OpenRouter `:free` model is free. The registry (and routing) therefore classify
each *model*. A free-tier grant is restricted to `billing_class: free` models
and can never fall back into a paid one.

## Task policy v2 additions

| Field | Meaning |
| --- | --- |
| `allowed_billing_classes` | When non-empty, only models in these classes satisfy the task. |
| `required_data_handling` | When set, only models with exactly this `data_handling` satisfy the task. |

## Approval process

1. `model_discovery.py` (operator-run) queries provider model listings and writes
   `config/discovered_models.json` with `approval_status: discovered`.
2. Discovered models are not routable (`enabled` is derived to `false`).
3. An administrator approves a model by copying it into
   `config/model_registry.json` with pricing, capabilities, billing class, and
   `approval_status: approved`.
4. `MODEL_REGISTRY_MAX_AGE_DAYS` still gates freshness in production/staging.

## Validation

`ModelRegistry` fails closed on: unknown `billing_class` / `auth` / `adapter` /
`approval_status`, a `free` model with a price, a capability flag without its
capability, a model referencing an unknown provider, and duplicate ids.

`tests/test_provider_auth_formats.py` locks the per-provider credential formats
above: Azure's `api-key` header, Google's `?key=`, Bedrock's SigV4 chain, and
Bearer for every other compatible provider.
