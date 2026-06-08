# WS4 — Complexity-Tier Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add complexity-tier routing and cheap/free model tiers (OpenRouter free, Gemini Flash family) to `ModelRouter`, so low-reasoning tasks prefer free models with automatic fallback to reliable paid models.

**Architecture:** Pure routing/config change in `ai_router_core.py`. A new `ComplexityTier` enum + `TASK_COMPLEXITY` (task→tier) + `TIER_MODELS` (tier→ordered providers) drive a new `select_chain()` that returns an availability-ordered list of `ModelConfig`. `AICommandLayer._execute_with_retry` walks that chain on failure. `_call_llm` stays a stub (Option A — no real provider calls). The old static `_init_fallbacks`/`fallback_chain`/`get_fallback_model` mechanism is removed (subsumed by `select_chain`).

**Tech Stack:** Python 3.11 (target; sandbox is 3.12 but the module imports with **no external deps**, so it runs here), stdlib only (`os`, `enum`, `dataclasses`).

**Spec:** `docs/superpowers/specs/2026-06-08-ws4-model-routing-design.md`

**Verification reality:** `ai_router_core` imports and `ModelRouter()` constructs in this sandbox with no API keys. So unlike most of this repo, WS4 is verified with a **real import+assert smoke test** (`tests/test_model_routing.py`), not just `py_compile`. There is no `pytest`/test suite in this repo today, so the test file is a **plain runnable script** using `assert` + `python3 tests/test_model_routing.py` (exit 0 = pass). Do NOT assume pytest is installed.

---

## File Structure

- **Modify:** `ai_router_core.py`
  - `import os` (new, top of file ~line 47)
  - `ModelProvider` enum (line 138) — add 3 providers
  - `ModelConfig` dataclass (line 894) — add `api_key_env`, `is_free` fields
  - new `ComplexityTier` enum (insert just before `class ModelRouter`, line 921)
  - `ModelRouter` (line 921) — add `TASK_COMPLEXITY`, `TIER_MODELS`; rewrite `__init__`, `_init_models`, `select_model`; add `select_chain`, `_validate_coverage`; remove `_init_fallbacks`, `get_fallback_model`
  - `AICommandLayer._execute_with_retry` (line 1361) — walk the chain
- **Create:** `tests/test_model_routing.py` — standalone assert-based smoke test

---

## Task 1: Smoke-test harness (failing first)

**Files:**
- Create: `tests/test_model_routing.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_model_routing.py`:

```python
"""
WS4 routing smoke test. Standalone (no pytest dependency): run with
    python3 tests/test_model_routing.py
Exit 0 = all asserts passed. Imports ai_router_core directly (no external deps).
"""
import os
import sys

# allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    ModelRouter, ModelProvider, ComplexityTier, TaskType,
    AIRequest, UserContext, UserRole, SubscriptionTier,
)


def _req(task: TaskType, tier: SubscriptionTier = SubscriptionTier.FOUNDER_PRO) -> AIRequest:
    ctx = UserContext(
        user_id="u_test", role=UserRole.FOUNDER, subscription_tier=tier,
        credits_remaining=100, project_id="p_test", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0,
    )
    return AIRequest(task_type=task, user_context=ctx, input_data={})


def test_construction_validates():
    ModelRouter()  # must not raise (exercises _validate_coverage)


def test_every_task_resolves_nonempty():
    r = ModelRouter()
    for task in TaskType:
        chain = r.select_chain(_req(task))
        assert chain, f"empty chain for {task}"


def test_trivial_is_free_first_when_keyed():
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        r = ModelRouter()
        chain = r.select_chain(_req(TaskType.MATCHING))  # TRIVIAL
        assert chain[0].provider == ModelProvider.OPENROUTER_FREE, chain[0].provider
    finally:
        del os.environ["OPENROUTER_API_KEY"]


def test_trivial_nonempty_when_unkeyed():
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.MATCHING))
    assert chain, "chain must be non-empty even with no keys"


def test_free_subscription_never_premium():
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.UNICORN_ANALYSIS, SubscriptionTier.FREE))
    providers = {c.provider for c in chain}
    assert ModelProvider.OPENAI_GPT4 not in providers
    assert ModelProvider.ANTHROPIC_CLAUDE not in providers


def test_embeddings_routes_to_cohere():
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.EMBEDDINGS))
    assert chain[0].provider == ModelProvider.COHERE_EMBED


def test_select_model_is_chain_head():
    r = ModelRouter()
    req = _req(TaskType.CHAT)
    assert r.select_model(req).provider == r.select_chain(req)[0].provider


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} routing tests passed.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_model_routing.py`
Expected: FAIL — `ImportError: cannot import name 'ComplexityTier' from 'ai_router_core'` (it does not exist yet).

---

## Task 2: Add `import os` and new providers

**Files:**
- Modify: `ai_router_core.py` (imports ~line 47; `ModelProvider` line 138)

- [ ] **Step 1: Add `import os`**

In the import block (after `import math`, around line 50), add:

```python
import os
```

- [ ] **Step 2: Add the three new providers to `ModelProvider`**

Replace the `ModelProvider` enum body (lines 138-144) so it reads:

```python
class ModelProvider(Enum):
    OPENAI_GPT4       = "openai_gpt4"
    OPENAI_GPT4_MINI  = "openai_gpt4_mini"
    ANTHROPIC_CLAUDE  = "anthropic_claude"
    ANTHROPIC_HAIKU   = "anthropic_claude_haiku"
    LOCAL_LLAMA       = "local_llama"
    COHERE_EMBED      = "cohere_embed"
    GEMINI_FLASH      = "gemini_flash"
    GEMINI_FLASH_LITE = "gemini_flash_lite"
    OPENROUTER_FREE   = "openrouter_free"
```

- [ ] **Step 3: Verify the module still imports**

Run: `python3 -c "import ai_router_core; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add ai_router_core.py
git commit -m "feat(ws4): add os import + Gemini/OpenRouter providers"
```

---

## Task 3: Extend `ModelConfig` with availability fields

**Files:**
- Modify: `ai_router_core.py` (`ModelConfig` dataclass, line 894)

- [ ] **Step 1: Add the two optional fields**

Replace the `ModelConfig` dataclass (lines 893-900) with:

```python
@dataclass
class ModelConfig:
    provider:           ModelProvider
    model_name:         str
    cost_per_1k_tokens: float
    max_context_length: int
    strengths:          List[str]
    use_cases:          List[TaskType]
    api_key_env:        str  = ""      # env var required for this provider to be "available"; "" = always available
    is_free:            bool = False   # reporting only
```

- [ ] **Step 2: Verify import**

Run: `python3 -c "import ai_router_core; print('ok')"`
Expected: `ok` (existing `ModelConfig(...)` calls still valid — new fields are defaulted).

- [ ] **Step 3: Commit**

```bash
git add ai_router_core.py
git commit -m "feat(ws4): add api_key_env + is_free to ModelConfig"
```

---

## Task 4: Add `ComplexityTier` enum

**Files:**
- Modify: `ai_router_core.py` (insert directly before `class ModelRouter`, line 921)

- [ ] **Step 1: Insert the enum**

Immediately before the `class ModelRouter:` line, add:

```python
class ComplexityTier(Enum):
    HEAVY    = "heavy"      # deep reasoning, coding, scoring
    STANDARD = "standard"   # long-form generation
    LIGHT    = "light"      # chat, summaries, dashboard glue
    TRIVIAL  = "trivial"    # classification, moderation, notifications


```

- [ ] **Step 2: Verify import**

Run: `python3 -c "from ai_router_core import ComplexityTier; print(ComplexityTier.HEAVY.value)"`
Expected: `heavy`

- [ ] **Step 3: Commit**

```bash
git add ai_router_core.py
git commit -m "feat(ws4): add ComplexityTier enum"
```

---

## Task 5: Register the new models in `_init_models` + key-env on existing

**Files:**
- Modify: `ai_router_core.py` (`_init_models`, lines 990-1017)

- [ ] **Step 1: Replace `_init_models` body**

Replace the whole `_init_models` method (lines 990-1017) with:

```python
    def _init_models(self) -> Dict[ModelProvider, ModelConfig]:
        return {
            ModelProvider.OPENAI_GPT4: ModelConfig(
                ModelProvider.OPENAI_GPT4, "gpt-4-turbo", 0.01, 128_000,
                ["deep reasoning", "unicorn scoring", "code"],
                [TaskType.IDEA_EVALUATION, TaskType.UNICORN_ANALYSIS],
                api_key_env="OPENAI_API_KEY",
            ),
            ModelProvider.OPENAI_GPT4_MINI: ModelConfig(
                ModelProvider.OPENAI_GPT4_MINI, "gpt-4o-mini", 0.0002, 128_000,
                ["speed", "low cost", "chat"],
                [TaskType.CHAT, TaskType.TOUR_GUIDE],
                api_key_env="OPENAI_API_KEY",
            ),
            ModelProvider.ANTHROPIC_CLAUDE: ModelConfig(
                ModelProvider.ANTHROPIC_CLAUDE, "claude-sonnet-4-6", 0.003, 200_000,
                ["long context", "business plans", "strategy"],
                [TaskType.BUSINESS_PLAN, TaskType.SUMMARY],
                api_key_env="ANTHROPIC_API_KEY",
            ),
            ModelProvider.ANTHROPIC_HAIKU: ModelConfig(
                ModelProvider.ANTHROPIC_HAIKU, "claude-haiku-4-5-20251001", 0.00025, 200_000,
                ["speed", "classification", "matching"],
                [TaskType.MATCHING, TaskType.PROFILE_ANALYSIS],
                api_key_env="ANTHROPIC_API_KEY",
            ),
            ModelProvider.COHERE_EMBED: ModelConfig(
                ModelProvider.COHERE_EMBED, "embed-english-v3.0", 0.0001, 512,
                ["embeddings", "semantic search"],
                [TaskType.EMBEDDINGS],
                api_key_env="COHERE_API_KEY",
            ),
            ModelProvider.GEMINI_FLASH: ModelConfig(
                ModelProvider.GEMINI_FLASH, "gemini-2.0-flash", 0.0001, 1_000_000,
                ["speed", "low cost", "light reasoning"],
                [TaskType.CHAT, TaskType.FEED_INTELLIGENCE],
                api_key_env="GEMINI_API_KEY",
            ),
            ModelProvider.GEMINI_FLASH_LITE: ModelConfig(
                ModelProvider.GEMINI_FLASH_LITE, "gemini-2.0-flash-lite", 0.00004, 1_000_000,
                ["cheapest", "classification", "notifications"],
                [TaskType.MATCHING, TaskType.DISCUSSION_MODERATION],
                api_key_env="GEMINI_API_KEY",
            ),
            ModelProvider.OPENROUTER_FREE: ModelConfig(
                ModelProvider.OPENROUTER_FREE, "meta-llama/llama-3.3-70b-instruct:free",
                0.0, 128_000,
                ["free", "light reasoning", "high volume"],
                [TaskType.MATCHING, TaskType.FIELD_FEEDBACK_ANALYSIS],
                api_key_env="OPENROUTER_API_KEY", is_free=True,
            ),
        }
```

- [ ] **Step 2: Verify all 8 models construct**

Run: `python3 -c "from ai_router_core import ModelRouter; print(len(ModelRouter()._init_models()))"`
Expected: `8`

(Note: this still constructs the OLD `__init__` which calls `_init_fallbacks`; that's fine until Task 6.)

- [ ] **Step 3: Commit**

```bash
git add ai_router_core.py
git commit -m "feat(ws4): register Gemini + OpenRouter models, add key-env to all"
```

---

## Task 6: Tier maps, `select_chain`, `_validate_coverage`; remove old fallback

**Files:**
- Modify: `ai_router_core.py` (`ModelRouter` `__init__` line 986; `_init_fallbacks` 1019-1025; `select_model` 1027-1034; `get_fallback_model` 1036-1038). Keep `TASK_MAP` (lines 924-984) as-is — it is left intact for reference/back-compat but no longer used by selection.

- [ ] **Step 1: Replace `__init__` through `get_fallback_model`**

Replace the block from `def __init__(self) -> None:` (line 986) through the end of `get_fallback_model` (line 1038) with the following. This adds the tier maps, `select_chain`, `_validate_coverage`, rewrites `__init__` and `select_model`, and removes `_init_fallbacks` + `get_fallback_model`:

```python
    TASK_COMPLEXITY: Dict[TaskType, ComplexityTier] = {
        # HEAVY — deep reasoning / coding / scoring
        TaskType.IDEA_EVALUATION:     ComplexityTier.HEAVY,
        TaskType.UNICORN_ANALYSIS:    ComplexityTier.HEAVY,
        TaskType.CODE_REVIEW:         ComplexityTier.HEAVY,
        TaskType.RISK_ANALYSIS:       ComplexityTier.HEAVY,
        TaskType.STARTUP_STRATEGY:    ComplexityTier.HEAVY,
        TaskType.PIVOT_INTELLIGENCE:  ComplexityTier.HEAVY,
        TaskType.PRODUCT_FEASIBILITY: ComplexityTier.HEAVY,
        TaskType.TECH_STACK_DESIGN:   ComplexityTier.HEAVY,
        TaskType.INVESTOR_EVI:        ComplexityTier.HEAVY,
        TaskType.PROBLEM_ANALYSIS:    ComplexityTier.HEAVY,
        TaskType.FEASIBILITY_ESTIMATE: ComplexityTier.HEAVY,
        TaskType.APP_SCAFFOLD_GENERATION: ComplexityTier.HEAVY,
        # STANDARD — long-form generation
        TaskType.BUSINESS_PLAN:            ComplexityTier.STANDARD,
        TaskType.EXECUTIVE_SUMMARY:        ComplexityTier.STANDARD,
        TaskType.MARKET_INTELLIGENCE:      ComplexityTier.STANDARD,
        TaskType.FINANCE_STRATEGY:         ComplexityTier.STANDARD,
        TaskType.INVESTOR_READINESS:       ComplexityTier.STANDARD,
        TaskType.INVESTOR_SIGNAL:          ComplexityTier.STANDARD,
        TaskType.TRAINING_GENERATION:      ComplexityTier.STANDARD,
        TaskType.SUMMARY:                  ComplexityTier.STANDARD,
        TaskType.MARKET_SURVEY_SIMULATION: ComplexityTier.STANDARD,
        TaskType.EXECUTION_ROADMAP:        ComplexityTier.STANDARD,
        TaskType.ORG_SPHERE:               ComplexityTier.STANDARD,
        TaskType.SOLUTION_SYNTHESIS:       ComplexityTier.STANDARD,
        TaskType.DEPLOYMENT_PLANNING:      ComplexityTier.STANDARD,
        TaskType.GRANT_MATCHING:           ComplexityTier.STANDARD,
        TaskType.DOCUMENT_EXECUTIVE_SUMMARY:    ComplexityTier.STANDARD,
        TaskType.DOCUMENT_BUSINESS_PLAN:        ComplexityTier.STANDARD,
        TaskType.DOCUMENT_PITCH_DECK:           ComplexityTier.STANDARD,
        TaskType.DOCUMENT_INVESTOR_REPORT:      ComplexityTier.STANDARD,
        TaskType.DOCUMENT_UNICORN_REPORT:       ComplexityTier.STANDARD,
        TaskType.DOCUMENT_PRODUCT_ROADMAP:      ComplexityTier.STANDARD,
        TaskType.DOCUMENT_FINANCIAL_PROJECTION: ComplexityTier.STANDARD,
        TaskType.DOCUMENT_MARKET_RESEARCH:      ComplexityTier.STANDARD,
        # LIGHT — chat / glue / light reasoning
        TaskType.CHAT:                   ComplexityTier.LIGHT,
        TaskType.TOUR_GUIDE:             ComplexityTier.LIGHT,
        TaskType.WORKSPACE_ASSISTANT:    ComplexityTier.LIGHT,
        TaskType.DASHBOARD_INTELLIGENCE: ComplexityTier.LIGHT,
        TaskType.FEED_INTELLIGENCE:      ComplexityTier.LIGHT,
        TaskType.RECOMMENDATION_ENGINE:  ComplexityTier.LIGHT,
        TaskType.GSIS_COMPUTE:           ComplexityTier.LIGHT,
        TaskType.IMPACT_PREDICTION:      ComplexityTier.LIGHT,
        TaskType.PROBLEM_DISCOVERY:      ComplexityTier.LIGHT,
        TaskType.APP_DEPLOY_CONFIG:      ComplexityTier.LIGHT,
        # TRIVIAL — classification / moderation
        TaskType.MATCHING:                ComplexityTier.TRIVIAL,
        TaskType.PROFILE_ANALYSIS:        ComplexityTier.TRIVIAL,
        TaskType.ADMIN_MONITOR:           ComplexityTier.TRIVIAL,
        TaskType.SOLUTION_MATCHING:       ComplexityTier.TRIVIAL,
        TaskType.DISCUSSION_MODERATION:   ComplexityTier.TRIVIAL,
        TaskType.FIELD_FEEDBACK_ANALYSIS: ComplexityTier.TRIVIAL,
        # EMBEDDINGS intentionally omitted — special-cased to Cohere in select_chain.
    }

    TIER_MODELS: Dict[ComplexityTier, List[ModelProvider]] = {
        ComplexityTier.HEAVY:    [ModelProvider.OPENAI_GPT4, ModelProvider.ANTHROPIC_CLAUDE,
                                  ModelProvider.OPENAI_GPT4_MINI],
        ComplexityTier.STANDARD: [ModelProvider.ANTHROPIC_CLAUDE, ModelProvider.OPENAI_GPT4,
                                  ModelProvider.ANTHROPIC_HAIKU],
        ComplexityTier.LIGHT:    [ModelProvider.GEMINI_FLASH, ModelProvider.OPENAI_GPT4_MINI,
                                  ModelProvider.ANTHROPIC_HAIKU],
        ComplexityTier.TRIVIAL:  [ModelProvider.OPENROUTER_FREE, ModelProvider.GEMINI_FLASH_LITE,
                                  ModelProvider.ANTHROPIC_HAIKU, ModelProvider.OPENAI_GPT4_MINI],
    }

    def __init__(self) -> None:
        self.model_configs = self._init_models()
        self._validate_coverage()

    def _validate_coverage(self) -> None:
        for task in TaskType:
            if task is TaskType.EMBEDDINGS:
                continue
            if task not in self.TASK_COMPLEXITY:
                raise ValueError(f"TASK_COMPLEXITY missing tier for {task}")
        for tier, providers in self.TIER_MODELS.items():
            for prov in providers:
                if prov not in self.model_configs:
                    raise ValueError(f"TIER_MODELS[{tier}] references unknown provider {prov}")

    @staticmethod
    def _is_available(cfg: ModelConfig) -> bool:
        return not cfg.api_key_env or bool(os.environ.get(cfg.api_key_env))

    def _ordered_configs(self, providers: List[ModelProvider]) -> List[ModelConfig]:
        """Map providers -> configs, eligible (key present) first, none dropped."""
        configs = [self.model_configs[p] for p in providers if p in self.model_configs]
        eligible   = [c for c in configs if self._is_available(c)]
        ineligible = [c for c in configs if not self._is_available(c)]
        ordered, seen = [], set()
        for c in eligible + ineligible:
            if c.provider not in seen:
                ordered.append(c)
                seen.add(c.provider)
        return ordered

    def select_chain(self, request: AIRequest) -> List[ModelConfig]:
        """Ordered fallback chain of models for a request (never empty)."""
        if request.task_type is TaskType.EMBEDDINGS:
            return [self.model_configs[ModelProvider.COHERE_EMBED]]
        if request.user_context.subscription_tier == SubscriptionTier.FREE:
            return self._ordered_configs(self.TIER_MODELS[ComplexityTier.TRIVIAL])
        tier = self.TASK_COMPLEXITY.get(request.task_type, ComplexityTier.LIGHT)
        return self._ordered_configs(self.TIER_MODELS[tier])

    def select_model(self, request: AIRequest) -> ModelConfig:
        return self.select_chain(request)[0]
```

- [ ] **Step 2: Run the smoke test (now it should pass)**

Run: `python3 tests/test_model_routing.py`
Expected: prints `PASS test_...` for each test and `All 7 routing tests passed.`

- [ ] **Step 3: py_compile gate**

Run: `python3 -m py_compile ai_router_core.py`
Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add ai_router_core.py tests/test_model_routing.py
git commit -m "feat(ws4): complexity-tier select_chain + coverage guard; drop static fallback"
```

---

## Task 7: Walk the chain in `_execute_with_retry`

**Files:**
- Modify: `ai_router_core.py` (`AICommandLayer.process_request` ~line 1353-1354; `_execute_with_retry` lines 1361-1383)

- [ ] **Step 1: Pass the chain into retry**

In `process_request`, replace these two lines (around 1353-1354):

```python
        model_config = self.model_router.select_model(request)
        response     = await self._execute_with_retry(model_config, prompt, request)
```

with:

```python
        chain    = self.model_router.select_chain(request)
        response = await self._execute_with_retry(chain, prompt, request)
```

- [ ] **Step 2: Rewrite `_execute_with_retry` to walk the chain**

Replace the entire `_execute_with_retry` method (lines 1361-1383) with:

```python
    async def _execute_with_retry(self, chain: List[ModelConfig],
                                  prompt: str, request: AIRequest) -> AIResponse:
        last_exc: Optional[Exception] = None
        for attempt, model_config in enumerate(chain):
            try:
                output = await self._call_llm(model_config, prompt, request)
                return AIResponse(
                    task_type=request.task_type,
                    output=output["text"],
                    model_used=model_config.model_name,
                    tokens_used=output["tokens"],
                    cost=round((output["tokens"] / 1000) * model_config.cost_per_1k_tokens, 6),
                    confidence_score=output.get("confidence", 1.0),
                    execution_time_ms=output["duration_ms"],
                    metadata={"attempt": attempt + 1,
                              "provider": model_config.provider.value},
                )
            except Exception as exc:  # noqa: BLE001 — try next model in chain
                last_exc = exc
                continue
        raise last_exc if last_exc else RuntimeError("empty model chain")
```

- [ ] **Step 3: py_compile gate**

Run: `python3 -m py_compile ai_router_core.py`
Expected: no output, exit 0.

- [ ] **Step 4: Run the module's own demo (smoke that the brain still works end-to-end)**

Run: `python3 -c "import asyncio, ai_router_core as m; asyncio.run(m._demo())"`
Expected: runs without exception (prints the demo output; `_call_llm` returns the placeholder, so an `AIResponse` is produced via `chain[0]`).

- [ ] **Step 5: Re-run routing tests**

Run: `python3 tests/test_model_routing.py`
Expected: `All 7 routing tests passed.`

- [ ] **Step 6: Commit**

```bash
git add ai_router_core.py
git commit -m "feat(ws4): AICommandLayer walks the model chain on failure"
```

---

## Task 8: Final verification + push + PR

**Files:** none (verification only)

- [ ] **Step 1: Full compile of touched + dependent modules**

Run: `python3 -m py_compile ai_router_core.py integration_guide.py agent_orchestration.py main.py`
Expected: no output, exit 0 (confirms no downstream caller broke — `select_model` signature preserved).

- [ ] **Step 2: Confirm no dangling references to removed symbols**

Run: `grep -rn "_init_fallbacks\|fallback_chain\|get_fallback_model" *.py`
Expected: **no output** (all three removed; the only previous caller was `_execute_with_retry`, now rewritten).

- [ ] **Step 3: Run routing tests one final time**

Run: `python3 tests/test_model_routing.py`
Expected: `All 7 routing tests passed.`

- [ ] **Step 4: Verify branch, push, open PR (HOLD MERGE for user)**

```bash
git branch --show-current   # must be feat/model-routing-tiers
git rev-parse --short HEAD
git push -u origin feat/model-routing-tiers
gh pr create --base main --head feat/model-routing-tiers \
  --title "WS4: complexity-tier model routing + cheap/free model tiers" \
  --body "Implements docs/superpowers/specs/2026-06-08-ws4-model-routing-design.md. Adds Gemini Flash + OpenRouter-free providers, ComplexityTier routing (HEAVY/STANDARD/LIGHT/TRIVIAL), free-first select_chain with env-gated availability, chain-walking fallback. _call_llm stays a stub (Option A). Verified via tests/test_model_routing.py (7 asserts) + py_compile."
```

Do **not** merge — leave the PR open for user review (matches established workflow).

---

## Self-Review (completed by plan author)

- **Spec coverage:** new providers → Task 2/5; `ModelConfig` fields → Task 3; `ComplexityTier` → Task 4; `TASK_COMPLEXITY`/`TIER_MODELS` → Task 6; `select_chain` + FREE-tier + EMBEDDINGS special-case + availability partition → Task 6; remove old fallback → Task 6 + verified Task 8.2; `_execute_with_retry` chain walk → Task 7; `_validate_coverage` fail-fast → Task 6; verification (py_compile + import asserts, no keys) → Tasks 1/6/7/8. All spec sections mapped.
- **Placeholder scan:** none — every code step shows full code; every run step shows command + expected output.
- **Type consistency:** `select_chain(request) -> List[ModelConfig]` defined Task 6, consumed Task 7; `_ordered_configs`, `_is_available`, `_validate_coverage` all defined and referenced consistently; `ModelConfig.api_key_env`/`is_free` defined Task 3, used Task 5/6; smoke test imports only symbols that exist after Task 6.
- **Note for executor:** Tasks must run in order — the smoke test (Task 1) intentionally fails until Task 6. Line numbers reference the pre-edit file; after each edit subsequent line numbers shift, so anchor on the shown code, not the numbers.
