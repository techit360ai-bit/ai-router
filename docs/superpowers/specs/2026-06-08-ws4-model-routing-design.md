# WS4 — Complexity-Tier Model Routing with Cheap/Free Model Tiers

- **Date:** 2026-06-08
- **Repo:** ai-router (`/home/faithsax/ai-router`)
- **Branch:** `feat/model-routing-tiers`
- **Status:** Approved design, pending spec review

## Problem

`ModelRouter` in `ai_router_core.py` already routes each `TaskType` to a provider
and supports vendor fallback, but:

- It only knows 5 providers (OpenAI GPT-4-turbo / GPT-4o-mini, Claude Sonnet 4.6 /
  Haiku 4.5, Cohere embed). No cheap-but-capable or free options.
- Routing intent is implicit in a flat `TASK_MAP` dict — "this is a low-reasoning
  task, send it somewhere cheap" is not a first-class concept.
- Low-reasoning, high-volume tasks (chat, feed intelligence, recommendation,
  classification, moderation, and — coming in WS1 — notifications/email) pay
  premium-ish model costs.

Goal: route by **task complexity**, and add **cheap + free** models (OpenRouter
free tiers, Gemini Flash family) as the preferred path for low-reasoning work,
with automatic fallback to reliable paid models.

## Scope

- **In scope:** `ai_router_core.py` routing/config only.
- **Out of scope (deferred):**
  - Real provider API calls. `_call_llm()` stays a stub returning a placeholder
    (this is **Option A**, chosen by the user). Today nothing in the system
    actually calls an LLM; this change is purely about *which* model would be
    chosen and in *what fallback order*.
  - A dedicated `NOTIFICATION` / `EMAIL` `TaskType` — WS1 (messaging layer) will
    add those and tag them `TRIVIAL`.
  - `requirements.txt` changes — no new SDK is needed for the config-only change
    (OpenRouter is OpenAI-compatible via `base_url` on the existing `openai`
    SDK; Gemini would later use `httpx` / the OpenAI-compat endpoint).

## Design

### 1. New providers

Add to the `ModelProvider` enum and `ModelRouter._init_models()`:

| Provider enum        | `model_name`                              | `cost_per_1k_tokens` | `api_key_env`        | `is_free` |
|----------------------|-------------------------------------------|----------------------|----------------------|-----------|
| `GEMINI_FLASH`       | `gemini-2.0-flash`                        | 0.0001               | `GEMINI_API_KEY`     | False     |
| `GEMINI_FLASH_LITE`  | `gemini-2.0-flash-lite`                   | 0.00004              | `GEMINI_API_KEY`     | False     |
| `OPENROUTER_FREE`    | `meta-llama/llama-3.3-70b-instruct:free`  | 0.0                  | `OPENROUTER_API_KEY` | True      |

Existing 5 providers get `api_key_env` populated too:
- `OPENAI_GPT4`, `OPENAI_GPT4_MINI` → `OPENAI_API_KEY`
- `ANTHROPIC_CLAUDE`, `ANTHROPIC_HAIKU` → `ANTHROPIC_API_KEY`
- `COHERE_EMBED` → `COHERE_API_KEY`

### 2. Extend `ModelConfig`

Add two optional fields with defaults so all existing positional/`ModelConfig(...)`
constructions keep working:

```python
@dataclass
class ModelConfig:
    provider:           ModelProvider
    model_name:         str
    cost_per_1k_tokens: float
    max_context_length: int
    strengths:          List[str]
    use_cases:          List[TaskType]
    api_key_env:        str  = ""      # env var that must be set for this provider to be "available"
    is_free:            bool = False   # reporting only
```

### 3. Complexity tiers

New enum + two module/class-level maps:

```python
class ComplexityTier(Enum):
    HEAVY    = "heavy"      # deep reasoning, coding, scoring
    STANDARD = "standard"   # long-form generation
    LIGHT    = "light"      # chat, summaries, dashboard glue
    TRIVIAL  = "trivial"    # classification, moderation, notifications
```

`TASK_COMPLEXITY: Dict[TaskType, ComplexityTier]` covers **all 51 task types**,
derived from today's `TASK_MAP` intent:

- **HEAVY** — `IDEA_EVALUATION`, `UNICORN_ANALYSIS`, `CODE_REVIEW`, `RISK_ANALYSIS`,
  `STARTUP_STRATEGY`, `PIVOT_INTELLIGENCE`, `PRODUCT_FEASIBILITY`,
  `TECH_STACK_DESIGN`, `INVESTOR_EVI`, `PROBLEM_ANALYSIS`, `FEASIBILITY_ESTIMATE`,
  `APP_SCAFFOLD_GENERATION`.
- **STANDARD** — `BUSINESS_PLAN`, `EXECUTIVE_SUMMARY`, `MARKET_INTELLIGENCE`,
  `FINANCE_STRATEGY`, `INVESTOR_READINESS`, `INVESTOR_SIGNAL`,
  `TRAINING_GENERATION`, `SUMMARY`, `MARKET_SURVEY_SIMULATION`,
  `EXECUTION_ROADMAP`, `ORG_SPHERE`, `SOLUTION_SYNTHESIS`, `DEPLOYMENT_PLANNING`,
  `GRANT_MATCHING`, and all 8 `DOCUMENT_*`.
- **LIGHT** — `CHAT`, `TOUR_GUIDE`, `WORKSPACE_ASSISTANT`, `DASHBOARD_INTELLIGENCE`,
  `FEED_INTELLIGENCE`, `RECOMMENDATION_ENGINE`, `GSIS_COMPUTE`, `IMPACT_PREDICTION`,
  `PROBLEM_DISCOVERY`, `APP_DEPLOY_CONFIG`.
- **TRIVIAL** — `MATCHING`, `PROFILE_ANALYSIS`, `ADMIN_MONITOR`, `SOLUTION_MATCHING`,
  `DISCUSSION_MODERATION`, `FIELD_FEEDBACK_ANALYSIS`.
- **Special-cased** — `EMBEDDINGS` is not a chat tier; it routes directly to
  `COHERE_EMBED` (bypasses tier logic).

`TIER_MODELS: Dict[ComplexityTier, List[ModelProvider]]` (ordered preference):

```
HEAVY    -> [OPENAI_GPT4, ANTHROPIC_CLAUDE, OPENAI_GPT4_MINI]
STANDARD -> [ANTHROPIC_CLAUDE, OPENAI_GPT4, ANTHROPIC_HAIKU]
LIGHT    -> [GEMINI_FLASH, OPENAI_GPT4_MINI, ANTHROPIC_HAIKU]
TRIVIAL  -> [OPENROUTER_FREE, GEMINI_FLASH_LITE, ANTHROPIC_HAIKU, OPENAI_GPT4_MINI]   # free-first
```

### 4. Selection + fallback

Rework `ModelRouter`:

- **`select_chain(request) -> List[ModelConfig]`** — the core new method:
  1. `EMBEDDINGS` → `[COHERE_EMBED]`.
  2. If `subscription_tier == FREE`: use the TRIVIAL/free-first preference list
     regardless of task (preserves today's "free users get cheap models"
     behaviour, just with free models now in front).
  3. Otherwise: `tier = TASK_COMPLEXITY[task]`, providers = `TIER_MODELS[tier]`.
  4. **Partition by availability** (`api_key_env == "" or os.environ.get(api_key_env)`):
     eligible providers first, ineligible appended last (never drop any, since
     `_call_llm` is stubbed and the app may run with no keys). Result is always
     non-empty.
  5. Map providers → `ModelConfig`, dedupe preserving order, return.
- **`select_model(request) -> ModelConfig`** = `select_chain(request)[0]`
  (keeps the existing public method working).
- **Remove** the old static fallback mechanism — `_init_fallbacks`, the
  `fallback_chain` attribute, and `get_fallback_model` — since `select_chain`
  subsumes it and `_execute_with_retry` (the only caller of `get_fallback_model`)
  is updated below. No other module references them (verified by grep).
- **`AICommandLayer._execute_with_retry`** changes from a single fallback hop to
  walking the **chain**: it pulls `chain = select_chain(request)` and tries each
  `ModelConfig` in order until one succeeds or the chain is exhausted. `_call_llm`
  remains a stub.

### 5. Fail-fast coverage guard

`ModelRouter.__init__` calls `_validate_coverage()` which asserts:
- every `TaskType` (except `EMBEDDINGS`) has an entry in `TASK_COMPLEXITY`;
- every provider referenced in `TIER_MODELS` exists in `model_configs`.

A missing mapping raises at construction (fail-fast) instead of mid-request.

## Data flow

```
agent -> AICommandLayer.process_request(AIRequest)
           -> select_chain(request)                # [ModelConfig] ordered, eligible-first
           -> _execute_with_retry(chain, prompt)   # try chain[0], on error chain[1], ...
                -> _call_llm(model_config, ...)     # STUB (placeholder) — unchanged
```

## Testing / verification

`ai_router_core` imports with **no external SDK dependencies** and `ModelRouter()`
constructs in this sandbox — so verification runs here, no API keys required:

1. `python3 -m py_compile ai_router_core.py` — established gate.
2. Smoke test (standalone script, real import + asserts):
   - construct `ModelRouter()` (exercises `_validate_coverage`);
   - every one of the 51 `TaskType`s yields a non-empty `select_chain`;
   - a TRIVIAL task is **free-first** (`OPENROUTER_FREE`) when `OPENROUTER_API_KEY`
     is set, and still returns a non-empty chain when it is unset;
   - a `FREE`-subscription request never resolves to `OPENAI_GPT4` or
     `ANTHROPIC_CLAUDE`;
   - `EMBEDDINGS` → `COHERE_EMBED`.

## Risks / notes

- `_call_llm` remains a stub: this change has **no runtime LLM effect** until real
  provider calls are implemented (a future Option-B task). It is purely the
  routing/decision layer.
- Availability is env-gated but never blocking — with zero keys configured the
  router still returns a deterministic chain (ineligible providers included), so
  construction and selection never fail in a keyless dev/CI environment.
- Cost numbers are approximate list prices for reporting; they do not affect
  selection order (tiers do).
