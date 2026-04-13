# TECHIT AI INCUBATION PLATFORM v3.0
## Complete Unified AI Orchestration Layer -- Production Implementation

> **YOU ARE NOT BUILDING A GPT WRAPPER.**
> **YOU ARE BUILDING THE EXECUTION INTELLIGENCE LAYER FOR THE GLOBAL STARTUP ECOSYSTEM.**

---

## What Is TechIT?

TechIT solves the most critical failure in the global startup ecosystem:

> *90% of startups fail -- not because of bad technology, but because of strategy failure, execution failure, and lack of structured support. The top reasons: No market need (42%), Ran out of cash (29%), Wrong team (23%). These are all strategy and execution problems.*

TechIT introduces a new infrastructure category: **Startup Execution Infrastructure** -- a unified AI-native platform where startups validate, build, measure, and prove readiness to investors.

---

## Repository Structure

```
techit-ai-router/
├── ai_router_core.py          # Brain: 20 scoring models, 49 TaskTypes, model routing
├── agent_orchestration.py     # 33 agents + venture pipeline + event routing
├── database_schema.py         # 41 PostgreSQL tables + pgvector + billing schema
├── integration_guide.py       # 18 service classes -- every TechIT feature
├── billing_system.py          # Hybrid subscription+PAYG billing, paywalls, referrals
├── investor_evi.py            # EVI-I: 6-dimensional investor execution signal
├── training_module.py         # Adaptive training: time-to-MVP engine, 35 modules
├── idea_solution_hub.py       # Problem-Driven pathway, impact scoring, deployment engine
├── document_generation.py     # 8-type document factory, master prompt, export system
├── deployment_architecture.py # Docker, Kubernetes, Celery (14 jobs), cost model
├── app_scaffold.py            # Prompt -> Live App: scaffold engine, deploy config, stacks
└── README.md                  # This file
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│               TECHIT APPLICATION LAYER                           │
│  Dashboard * Incubation Hub * Workspace * Training * Feed        │
│  Investor Section * Org Sphere * Profile * Market Ready * Admin  │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│            TECHIT AI BRAIN  (TechITAIBrain singleton)            │
├────────────────┬──────────────────┬─────────────────────────────┤
│  AI Command    │  Model Router    │  Agent Orchestrator          │
│  Layer         │                  │                              │
│  • Safety gate │  GPT-4           │  34 Specialised Agents       │
│  • Rate limit  │  Claude Sonnet   │  VenturePipeline             │
│  • Credit deduct│ GPT-4o-mini     │  (10-agent sequential)       │
│  • Prompt build│  Claude Haiku    │                              │
│  • Audit log   │  Cohere Embed    │  Event -> Agent routing       │
└────────────────┴──────────────────┴─────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐   ┌────────────────┐   ┌─────────────────────────┐
│  PostgreSQL  │   │  Redis         │   │  External AI Services   │
│  + pgvector  │   │                │   │  OpenAI * Anthropic     │
│  42 tables   │   │  Cache * Queue │   │  Cohere * ElevenLabs    │
│  GSIS snaps  │   │  Rate limits   │   │  Pinecone * Stripe      │
│  EVI-I snaps │   │  Agent memory  │   │                         │
│  Billing     │   │  WCRS/GSIS     │   │                         │
└──────────────┘   └────────────────┘   └─────────────────────────┘
```

---

## All 20 Scoring Models

Every score is computed by `ScoringEngine` in `ai_router_core.py`.

| # | Score | Formula | Purpose |
|---|-------|---------|---------|
| 1 | **GSIS** | `0.15*PPS + 0.15*EVI + 0.20*MRS + 0.10*BSS + 0.10*RGS + 0.10*FRS + 0.05*CIS + 0.10*IIS + 0.05*CS` | Master composite score |
| 2 | **UPS** | Σ(driver × weight) × 10 | Unicorn probability (10 drivers) |
| 3 | **EVI** | `(0.30*MC + 0.20*RC⁻¹ + 0.20*IC + 0.20*CC − 0.10*ST) × 100` | Founder momentum |
| 4 | **EVI-I** | `(0.25*MDR + 0.20*IS + 0.15*TRV + 0.20*RTA + 0.10*UGM + 0.10*CEV)` | Investor execution signal |
| 5 | **RGS** | `0.35*MRR + 0.25*Users + 0.25*Retention + 0.15*Consistency` | Revenue health |
| 6 | **BSS** | `0.30*UX + 0.25*Perf + 0.25*NPS + 0.20*WTP` | Beta satisfaction |
| 7 | **CS** | `(Σ passed / total) × 100` | Compliance checklist |
| 8 | **MRS** | `0.25*EVI + 0.20*BSS + 0.20*RGS + 0.15*CS + 0.10*Global + 0.10*Stability` | Launch readiness |
| 9 | **TS** | `(Σ provided / total) × 100` | Transparency (investor visibility) |
| 10 | **FRS** | `0.30*Login + 0.30*Milestones + 0.20*Feedback + 0.10*Community + 0.10*Profile` | Founder reliability |
| 11 | **CIS** | `(Engagement + ContentValue + FollowerQuality) / 3` | Community influence |
| 12 | **IIS** | `(Views + Saves + ContactRequests + Watchlist) / 4` | Investor interest |
| 13 | **PPS** | `(CompletedTasks / TotalTasks) × QualityFactor × 100` | Product progress |
| 14 | **TSS** | `(SkillCoverage + Activity + Delivery + Collaboration) / 4` | Team strength |
| 15 | **WCRS** | `Base × QualityMultiplier × DecayFactor` | Marketplace ranking |
| 16 | **IS** | `0.30*MR + 0.25*Traction + 0.15*Team + 0.15*RiskInverse + 0.10*Growth + 0.05*Diff` | Investment attractiveness |
| 17 | **MatchScore** | `(0.30*Skill + 0.20*Goal + 0.15*Exec + 0.15*Avail + 0.10*Trust + 0.10*Domain) × 100` | Team compatibility |
| 18 | **Decay** | `e^(−0.02 × days_inactive)` | Anti-gaming inactivity penalty |
| 19 | **Impact Score** | `0.30*PA + 0.25*SEV + 0.20*SCALE + 0.15*SUS + 0.10*MEAS` | Idea & Solution Hub -- problem/solution severity |
| 20 | **Problem Priority Score** | `0.25*IS + 0.25*URG + 0.20*FUND + 0.15*POL + 0.15*TIME` | Global Problems Board ranking |

---

## All 33 Agents

### Incubation Hub (10 agents)
| Agent | Purpose | Min Tier | Credits |
|-------|---------|----------|---------|
| VentureIntakeAgent | Structures raw input -> Venture Data Model | Free | 1 |
| UnicornEvaluatorAgent | 10-driver UPS + Dileep Rao Benchmark | Builder | 2 |
| MarketIntelligenceAgent | TAM/SAM/SOM, competition, timing | Builder | 2 |
| ProductFeasibilityAgent | Build complexity, technical risk | Founder Pro | 2 |
| StartupStrategyAgent | GTM, pricing, growth, PMF path | Founder Pro | 3 |
| FinanceStrategyAgent | Capital efficiency, unit economics | Founder Pro | 2 |
| InvestorIntelligenceAgent | EVI-I + deal flow signals | Investor | 2 |
| BusinessPlanGeneratorAgent | Executive summary + 10-section plan | Investor | 6 |
| TechArchitectAgent | Full-stack architecture design | Founder Pro | 2 |
| PivotIntelligenceAgent | Pivot analysis + concept regeneration | Builder | 2 |

### Platform (11 agents)
| Agent | Purpose | Min Tier | Credits |
|-------|---------|----------|---------|
| TourGuideAgent | Daily momentum + decay enforcement | Free | 0 |
| AdaptiveTrainingAgent | Time-to-MVP curriculum (not fixed weeks) | Free | 1 |
| MatchingAgent | Vector + rules + LLM matching | Builder | 1 |
| RiskEvaluatorAgent | SWOT + key risks + team gaps | Builder | 2 |
| WorkspaceAssistantAgent | Task prioritisation + sprint planning | Free | 0 |
| FeedIntelligenceAgent | Community feed curation | Free | 0 |
| DashboardIntelligenceAgent | GSIS surface + real-time scores | Free | 0 |
| GSISComputeAgent | Global Startup Intelligence Score | Free | 1 |
| AIProfileAgent | Profile scoring + recommendations | Free | 1 |
| OrgSphereAgent | Organization structure intelligence | Founder Pro | 1 |
| AdminMonitorAgent | Abuse detection + anomaly monitoring | Enterprise | 0 |

### Idea & Solution Hub (10 agents)
| Agent | Purpose | Min Tier | Credits |
|-------|---------|----------|---------|
| ProblemAnalyzerAgent | Expands scope, builds stakeholder map | Free | 2 |
| SolutionSynthesizerAgent | Converts discussion to solution blueprint | Founder Pro | 3 |
| ImpactPredictorAgent | Predicts real-world impact across time horizons | Free | 1 |
| FeasibilityEstimatorAgent | Technical, operational, financial feasibility | Builder | 2 |
| ProblemDiscoveryAgent | Auto-discovers problems from external signals | Builder | 2 |
| SolutionMatcherAgent | Matches existing solutions globally to new problems | Builder | 2 |
| DeploymentPlannerAgent | Creates real-world deployment plans | Founder Pro | 2 |
| GrantMatcherAgent | Generates grant applications for funding | Founder Pro | 3 |
| DiscussionModeratorAgent | Summarises, clusters, and directs discussions | Free | 1 |
| FieldFeedbackAgent | Closes the Problem -> Deploy -> Optimise loop | Free | 1 |

### Document Generation (2 agents)
| Agent | Purpose | Min Tier | Credits |
|-------|---------|----------|---------|
| DocumentGenerationAgent | Orchestrates all 8 document types end-to-end | Builder | 2–4 |
| DocumentExportAgent | PDF, Notion, Google Doc, Slide Deck, shareable links | Free | 0 |

---

## Hybrid Billing System

Two tracks run **simultaneously**:

```
TRACK A -- Subscription (monthly plan)
  Includes monthly credit allocation.
  Unlocks feature tiers and paywalls.
  Subscription credits always deducted first.

TRACK B -- Pay-As-You-Go (PAYG)
  Purchased credit packs -- never expire.
  Activate when subscription credits exhaust.
  Higher per-credit rate than subscription.

HYBRID RESOLUTION:
  credit_cost = from_subscription + from_payg
  Subscription depleted first -> PAYG overflow automatically.
```

### Role-Based Plans

| Plan | Price | Credits/Month | Key Unlock |
|------|-------|--------------|-----------|
| Founder Free | $0 | 5 | Idea diagnostic |
| Founder Builder ⭐ | $29/mo | 150 | Full unicorn + matching |
| Founder Scale | $99/mo | 500 | Business plan + investor section |
| Collab Free | $0 | 5 | Profile only |
| Collab Pro ⭐ | $19/mo | 50 | Paid projects + priority matching |
| Collab Elite | $49/mo | 150 | Verified badge + top placement |
| Org Project | $299/project | 200 | AI team assembly |
| Org Growth ⭐ | $999/project | 500 | Dedicated PM + SLA |
| Org Enterprise | Custom | Unlimited | White-label |
| Investor Access | $1,500/yr | 500/yr | Full deal flow + EVI-I |
| Investor Institutional | $10,000/yr | Unlimited | Portfolio + cohort analytics |

### Paywall Philosophy
*"Let them taste value, then block progress."*

```
Idea scored 82% ->  block full roadmap    -> "Unlock Builder -- $29/month"
3 matches found ->  block contact         -> "Start Building -- $29/month"
Investor viewing -> block reply           -> "Unlock Scale -- $99/month"
```

---

## EVI-I -- Investor Execution Signal

The **EVI-I** (in `investor_evi.py`) answers: *"Is this team executing fast enough?"*

Six independent sub-dimensions, decay-adjusted:

```
EVI-I = 0.25*MDR + 0.20*IS + 0.15*TRV + 0.20*RTA + 0.10*UGM + 0.10*CEV

MDR  Milestone Delivery Rate        -- are they shipping what they committed?
IS   Iteration Speed                -- how fast do they learn?
TRV  Team Response Velocity         -- how fast do they respond to investors?
RTA  Revenue Traction Acceleration  -- is revenue compounding?
UGM  User Growth Momentum           -- user base growing faster over time?
CEV  Capital Efficiency Velocity    -- more output per dollar?

DecayFactor = e^(−0.02 × days_inactive)
EVI-I_adj   = EVI-I_raw × DecayFactor

Signals: 85+ 🔥 Exceptional | 70–84 🚀 Strong | 55–69 📈 Moderate | 40–54 ⏳ Slow | 0–39 🔴 Stalled
```

---

## Adaptive Training -- No Fixed Weeks

The training system (in `training_module.py`) **never says "Week 1"**.

Duration is computed by the **Time-to-MVP Engine**:

```
base_weeks  (from project stage)
× complexity_modifier  (technical skills, co-founder)
× team_modifier        (team size)
× pace_multiplier      (intensive: 0.60× | standard: 1.00× | part-time: 1.80×)
= estimated_weeks_to_mvp
```

**Examples from live test:**
- Solo non-technical founder, idea stage, 8h/week -> **18 weeks**, 144 hours
- Technical co-founder team, validation, 20h/week intensive -> **3.6 weeks**, 72 hours
- Post-MVP founder with revenue + investor interest -> **all 5 post-MVP tracks unlocked immediately**

**Two Curriculum Zones:**

Zone 1 -- Pre-MVP: Validation -> Build -> Launch (22 modules)
Zone 2 -- Post-MVP: Growth + Revenue + Fundraising + Scale + Operations (15 modules)

Post-MVP modules unlock conditionally:
- Growth -> requires `stage = beta`
- Revenue -> requires `has_revenue = true`
- Fundraising -> requires `investor_interest = true`
- Scale -> requires `team_size >= 3`

**Adaptive triggers** (real-time re-prioritisation):
```
mvp_shipped               -> Activate full post-MVP curriculum
investor_expressed_interest -> Fast-track fundraising track
revenue_went_live          -> Unlock revenue optimisation track
pivot_detected             -> Re-trigger validation modules
```

---

## Event -> Agent Routing

```python
{
  "idea_submitted":              ["VentureIntake", "RiskEvaluator", "Matching"],
  "user_login":                  ["TourGuide", "DashboardIntelligence", "GSISCompute"],
  "training_completed":          ["AdaptiveTraining"],
  "milestone_updated":           ["Dashboard", "TourGuide", "GSISCompute"],
  "mvp_shipped":                 ["AdaptiveTraining", "DashboardIntelligence"],
  "revenue_went_live":           ["AdaptiveTraining", "InvestorIntelligence"],
  "pivot_detected":              ["PivotIntelligence", "AdaptiveTraining"],
  "investor_expressed_interest": ["AdaptiveTraining", "InvestorIntelligence"],
  "investor_views":              ["InvestorIntelligence"],
  "profile_updated":             ["AIProfile"],
  "org_created":                 ["OrgSphere"],
  # Idea & Solution Hub events
  "problem_submitted":           ["ProblemAnalyzer", "SolutionMatcher"],
  "solution_converted":          ["SolutionSynthesizer", "ImpactPredictor", "FeasibilityEstimator"],
  "deployment_created":          ["DeploymentPlanner"],
  "field_feedback_submitted":    ["FieldFeedbackAgent"],
  # Document Generation events
  "document_requested":          ["DocumentGeneration"],
  "document_export_requested":   ["DocumentExport"],
}
```

---

## Idea & Solution Hub

The **Problem-Driven pathway** -- TechIT's edge over every other startup platform.

```
Most platforms start with: "I have a startup idea"
TechIT also serves:        "Here is a real-world problem that needs solving"
```

### Two Entry Pathways

```
A. IDEA-DRIVEN  (existing)  -- "I want to build X" -> Startup Builder
B. PROBLEM-DRIVEN (new)     -- "Here is a problem" -> Idea & Solution Hub
```

### Hub Sections (Route: /incubator/solutions)

| Section | Route | Description |
|---------|-------|-------------|
| 🌍 Global Problems Board | `/incubator/solutions/problems` | Submit and browse real-world problems |
| 💡 Idea Discussions | `/incubator/solutions/discussions` | Structured threads with AI moderation |
| 🛠 Solution Builder | `/incubator/solutions/builder` | Convert discussion -> Solution Project |
| 🚀 Deployments | `/incubator/solutions/deployments` | Real-world deployment management |
| 🌍 Global Impact Dashboard | `/incubator/solutions/impact` | Live impact metrics worldwide |
| 💰 Funding & Grants | `/incubator/solutions/funding` | AI-generated grant applications |

### Impact Scoring System

```
Impact Score = 0.30*PA + 0.25*SEV + 0.20*SCALE + 0.15*SUS + 0.10*MEAS
  PA    People affected (log-normalised)
  SEV   Severity (0–10)
  SCALE Scalability (0–10)
  SUS   Sustainability (0–10)
  MEAS  Measurability (0–10)

Problem Priority Score = 0.25*IS + 0.25*URG + 0.20*FUND + 0.15*POL + 0.15*TIME
  🔴 Critical (85+)    🟠 High Priority (65–84)
  🟡 Emerging (45–64)  🔵 Long-term Research (0–44)
```

### Solution Types Supported

| Type | Description | Funding Model |
|------|-------------|---------------|
| `startup_for_profit` | Commercial startup | Revenue |
| `social_initiative` | NGO / social enterprise | Grants + donations |
| `public_policy` | Government policy proposal | Government funding |
| `community_project` | Grassroots community initiative | Donations + CSR |
| `research_project` | Academic / scientific | Grants + development banks |
| `infrastructure` | Physical infrastructure program | Government + development banks |
| `service_based` | Non-SaaS service delivery | Revenue + grants |
| `hybrid` | Mixed model | Hybrid |

### Problem -> Solution -> Deployment -> Feedback Loop

```
User submits problem
      ↓
AI analysis + stakeholder map
      ↓
Community discusses (structured: Idea / Insight / Resource / Critique / Data)
      ↓
AI synthesises strongest direction
      ↓
Convert to Solution Project
      ↓
Run feasibility + impact prediction
      ↓
Create deployment plan (Pilot / NGO / Government / Startup / CSR)
      ↓
Deploy to real world
      ↓
Collect field feedback
      ↓
AI optimises -> loop repeats
```

### Problem Discovery Engine

TechIT finds problems **before** users submit them:

- **Sources:** News feeds * NGO reports (ReliefWeb) * Government open datasets * WHO data * Climate signals
- **Output:** Auto-generated `ProblemNode` candidates with AI classification
- **Schedule:** Runs daily at 6 AM via `problem_discovery_daily` Celery task

### API Endpoints (Idea & Solution Hub)

```
POST /api/v1/solutions/problems/submit              2 credits  Free+
GET  /api/v1/solutions/problems/board               0 credits  Free+
POST /api/v1/solutions/problems/{id}/analyze        2 credits  Builder+
GET  /api/v1/solutions/problems/discover            2 credits  Builder+
GET  /api/v1/solutions/problems/match/{id}          2 credits  Builder+
POST /api/v1/solutions/discussions/{id}/contribute  1 credit   Free+
GET  /api/v1/solutions/discussions/{id}/summary     1 credit   Free+
POST /api/v1/solutions/discussions/{id}/convert     3 credits  Founder Pro+
POST /api/v1/solutions/projects/{id}/feasibility    2 credits  Builder+
GET  /api/v1/solutions/projects/{id}/impact         1 credit   Free+
POST /api/v1/solutions/deployments/create           2 credits  Founder Pro+
POST /api/v1/solutions/deployments/{id}/feedback    1 credit   Free+
POST /api/v1/solutions/grants/generate              3 credits  Founder Pro+
GET  /api/v1/solutions/impact/global                0 credits  Free+
```

---

## Document Generation Engine

```
Founders spend weeks writing business plans.
Builders spend days making pitch decks.
TechIT generates everything in minutes.
```

### 8 Document Types

| # | Document | Pages | Credits | Min Tier |
|---|----------|-------|---------|----------|
| 1 | 🧾 Executive Summary | 1–2 | 2 | Builder |
| 2 | 📊 Full Business Plan | 10–25 | 4 | Investor |
| 3 | 🎯 Pitch Deck | 12 slides | 3 | Founder Pro |
| 4 | 📈 Investor Report | 8 | 3 | Investor |
| 5 | 🧠 Unicorn Analysis Report | 7 | 2 | Builder |
| 6 | 🛠 Product Roadmap | 5 | 2 | Founder Pro |
| 7 | 💰 Financial Projection | 5 | 2 | Founder Pro |
| 8 | 🧪 Market Research Report | 8 | 3 | Founder Pro |

### Options Panel

| Option | Choices |
|--------|---------|
| **Style** | Concise * Standard * Detailed |
| **Audience** | Founder Use * Investors * Accelerators |
| **Export Format** | PDF * Notion Doc * Google Doc * Slide Deck |
| **Investor Mode** | Off * On (adds risk scoring + recommendation page) |

### Investor Pack (One-Click)

```python
# POST /api/v1/documents/investor-pack  -- 8 credits, Investor+
# Generates all 4 in one call:
{
  "documents": [
    "executive_summary",   # 2 credits
    "pitch_deck",          # 3 credits (investor mode on)
    "business_plan",       # 4 credits
    "investor_report",     # 3 credits
  ],
  "investor_pack_url": "https://app.techit.io/documents/pack/{project_id}"
}
```

### Generation Flow

```
POST /api/v1/documents/generate
      ↓
Pull startup data from project record
      ↓
Pull analysis results (GSIS, EVI-I, Unicorn Score)
      ↓
DocumentPromptEngine assembles master prompt
  (system role + type template + style + audience + investor mode)
      ↓
AI call -> Claude Sonnet 4.6 (all long-form documents)
      ↓
Parse structured output by section schema
      ↓
Build exports: PDF URL * shareable link * Edit with AI URL
      ↓
Return preview + full content + all export options
```

### API Endpoints (Document Generation)

```
GET  /api/v1/documents/templates           0 credits  Free+
POST /api/v1/documents/generate            2–4 credits Builder+
POST /api/v1/documents/investor-pack       8 credits  Investor+
GET  /api/v1/documents/{id}/preview        0 credits  Free+
POST /api/v1/documents/{id}/edit           2 credits  Builder+
POST /api/v1/documents/{id}/share          0 credits  Free+
DELETE /api/v1/documents/{id}              0 credits  Free+
```

---

## Prompt -> Live App Engine

```
TechIT's defining edge.
Others give you plans.
TechIT gives you a running product.
```

### The Insight

Every competing platform -- Bolt.new, v0.dev, Lovable, Replit Agent -- generates code from a user prompt. They are fast. But they are **blind**. They know nothing about the market size, the unicorn potential score, the competitive landscape, the investor signals, or the decay factor. They generate code that runs but may build the wrong product.

TechIT generates code **from intelligence**. By the time the scaffold is generated, the platform has already:

- Scored the idea against 10 unicorn drivers
- Analysed the TAM/SAM/SOM
- Designed the optimal tech stack via `TechArchitectAgent`
- Computed a GSIS score
- Matched the founder with collaborators

The scaffold is not generic. It is specific to this startup's industry, revenue model, target customers, and validated architecture.

### How It Works

```
User types: "Build a student marketplace for my university"
                    ↓
VentureIntakeAgent      structures the idea into a Venture Data Model
UnicornEvaluatorAgent   scores it: 74% unicorn potential
MarketIntelligenceAgent analyses market: $2.1B TAM
TechArchitectAgent      designs: Next.js + Supabase + Stripe
AppScaffoldAgent        generates the scaffold         ← THE DEFINING EDGE
                    ↓
Scaffold output:
  ✅ 6 pages (Home, Dashboard, Listings, Checkout, Profile, Admin)
  ✅ Supabase schema (users, listings, transactions, reviews tables)
  ✅ 12 API routes (auth, listings CRUD, payments, notifications)
  ✅ .env.example template
  ✅ vercel.json + GitHub Actions CI/CD
  ✅ Step-by-step setup commands
                    ↓
User clicks: "Deploy to Vercel"  (1 click, 3 credits)
                    ↓
2 minutes later:
"Your app is live: https://student-market.vercel.app"
                    ↓
TechIT keeps tracking:
  GSIS * EVI-I * Decay Factor * Investor Signals * Momentum
```

### Supported Stacks

| Stack | Best For | Deploy Time |
|-------|----------|-------------|
| `nextjs_supabase` ⭐ | SaaS, marketplaces, dashboards (default) | ~2 min |
| `nextjs_prisma` | Complex relational data models | ~3 min |
| `react_firebase` | Real-time apps, chat, collaboration | ~2 min |
| `expo_supabase` | iOS + Android mobile apps | ~5 min |
| `fastapi_supabase` | B2B APIs, developer tools | ~2 min |

### API Endpoints

```
POST /api/v1/scaffold/generate          5 credits  Founder Pro+
GET  /api/v1/scaffold/{project_id}      0 credits  Free+
POST /api/v1/scaffold/{id}/deploy       3 credits  Founder Pro+
GET  /api/v1/scaffold/{id}/status       0 credits  Free+
GET  /api/v1/scaffold/{id}/live-url     0 credits  Free+
POST /api/v1/scaffold/{id}/download     0 credits  Free+
GET  /api/v1/scaffold/stacks            0 credits  Free+
```

### The "Wait... I Just Built a Product in Minutes?" Moment

This reaction is the growth engine. Every time a founder sees their live URL, they share it. Every share is a TechIT acquisition. Every acquisition becomes a GSIS data point. Every GSIS data point becomes an investor signal.

The loop:

```
Scaffold -> Live product -> Founder shares -> New user signs up
-> New idea submitted -> New scaffold generated -> Loop repeats
```

---

## Competitive Positioning

TechIT is not competing with any single platform. It is combining what they all do -- and doing it in one place, with AI.

| Platform | What They Do | What They Miss |
|----------|-------------|----------------|
| Bolt.new / v0.dev | Generate code fast from a prompt | No strategy, no scoring, no investors, no accountability |
| YC / Accelerators | Strategy + network | Slow (1 batch/year), exclusive (2% acceptance), manual |
| Notion / Linear | Workspace + project management | No AI intelligence, no investor layer, no scoring |
| AngelList / Carta | Investor matching + cap table | No product building, no execution tracking |
| Canopy / Visible | Investor reporting | No idea validation, no product, no training |
| Replit Agent | Code + deploy in browser | No market intelligence, no unicorn scoring, no deal flow |
| **TechIT** | **All of the above, unified, AI-native** | -- |

### Why Winners Win

Facebook was not the first social network. WhatsApp was not the first messaging app. Instagram was not the first photo sharing app. They won because they were the **simplest, fastest, and most focused** on the thing users actually needed.

TechIT's answer to "what is the one thing?":

> **From idea to investor-ready product -- without leaving the platform.**

Not "we help startups." Not "we connect founders." Not "we generate business plans."

**Idea -> Score -> Build -> Deploy -> Track -> Raise. All here. All AI-native.**

### The Formula

```
TechIT = (Bolt.new + YC Library + Notion + AngelList + Stripe Atlas) × AI
```

No other platform has all five. TechIT does. And they are unified -- data flows from idea evaluation into the scaffold, from the scaffold into investor signals, from investor signals into the EVI-I score.

That data flywheel is the moat.

---

## Installation Guide

### Table of Contents -- Installation

1. [System Requirements](#1-system-requirements)
2. [Obtaining API Keys](#2-obtaining-api-keys)
3. [Clone the Repository](#3-clone-the-repository)
4. [Environment Configuration](#4-environment-configuration)
5. [Docker -- Local Development Setup](#5-docker--local-development-setup)
6. [Database Initialisation](#6-database-initialisation)
7. [Verify All Services](#7-verify-all-services)
8. [Running the API](#8-running-the-api)
9. [Running Celery Workers](#9-running-celery-workers)
10. [Running Without Docker (Native Python)](#10-running-without-docker-native-python)
11. [Seeding the AI Prompt Registry](#11-seeding-the-ai-prompt-registry)
12. [Pinecone Vector Store Setup (Optional)](#12-pinecone-vector-store-setup-optional)
13. [Voice / Audio Setup (Optional)](#13-voice--audio-setup-optional)
14. [Running Tests](#14-running-tests)
15. [Production Deployment -- AWS](#15-production-deployment--aws)
16. [Production Deployment -- Kubernetes](#16-production-deployment--kubernetes)
17. [CI/CD Pipeline -- GitHub Actions](#17-cicd-pipeline--github-actions)
18. [Monitoring Setup](#18-monitoring-setup)
19. [Common Errors and Fixes](#19-common-errors-and-fixes)
20. [Post-Installation Checklist](#20-post-installation-checklist)

---

### 1. System Requirements

| Component | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Python | 3.11+ | 3.11.9 | 3.12 supported but 3.11 preferred |
| Docker Engine | 24.0+ | Latest stable | Required for containerised setup |
| Docker Compose | 2.20+ | Latest stable | `docker compose` v2 syntax |
| RAM | 8 GB | 16 GB | 16 GB strongly recommended with all services |
| Disk | 10 GB | 20 GB | PostgreSQL data + Docker images |
| CPU | 2 cores | 4+ cores | AI worker concurrency benefits from more |
| OS | Linux / macOS | Ubuntu 22.04 LTS | Windows via WSL2 only |

**Verify your environment before proceeding:**

```bash
# Python version -- must be 3.11 or higher
python3 --version
# Expected: Python 3.11.x or 3.12.x

# Docker version
docker --version
# Expected: Docker version 24.x.x or higher

# Docker Compose v2 syntax
docker compose version
# Expected: Docker Compose version v2.x.x

# Available disk space (need at least 10 GB free)
df -h .

# Available RAM
free -h   # Linux
vm_stat   # macOS
```

---

### 2. Obtaining API Keys

TechIT requires API keys from external services. Collect these before proceeding.

#### Required (platform will not start without these)

**OpenAI**
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign in -> click your profile -> **API keys**
3. Click **+ Create new secret key** -> name it `techit-dev`
4. Copy immediately -- it will not be shown again
5. Ensure your account has GPT-4 access (requires payment method on file)

**Anthropic**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in -> **API Keys** in the left sidebar
3. Click **+ Create Key** -> name it `techit-dev`
4. Copy the `sk-ant-...` key immediately

#### Strongly Recommended

**Stripe** (required for billing system to process payments)
1. Go to [dashboard.stripe.com](https://dashboard.stripe.com)
2. Navigate to **Developers -> API keys**
3. Copy the **Secret key** (`sk_test_...` for development, `sk_live_...` for production)
4. For webhooks: **Developers -> Webhooks -> Add endpoint** -> set URL to `https://yourdomain.com/api/v1/webhooks/stripe` -> copy the signing secret (`whsec_...`)

**Cohere** (fallback embeddings provider)
1. Go to [dashboard.cohere.com](https://dashboard.cohere.com)
2. **API Keys** -> **New Trial Key** (free tier available)
3. Copy the key

#### Optional

**Pinecone** (vector search at scale -- pgvector sufficient for < 100K users)
1. Go to [app.pinecone.io](https://app.pinecone.io) -> sign in
2. **API Keys** -> copy your key
3. Create an index named `techit-embeddings` with **1536 dimensions**, **cosine** metric

**ElevenLabs** (Tour Guide audio briefings)
1. Go to [elevenlabs.io](https://elevenlabs.io) -> sign in
2. Click your profile icon -> **Profile + API key**
3. Copy your API key

**AWS** (S3 for audio and document storage)
1. Go to AWS Console -> **IAM -> Users -> Create user**
2. Name: `techit-dev` -> attach policy `AmazonS3FullAccess`
3. **Security credentials -> Create access key** -> copy both keys
4. Create an S3 bucket named `techit-assets-dev` in your preferred region

---

### 3. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/techit/ai-router.git
cd ai-router

# Verify all 8 Python files are present
ls -1 *.py
# Expected output:
# ai_router_core.py
# agent_orchestration.py
# billing_system.py
# database_schema.py
# deployment_architecture.py
# integration_guide.py
# investor_evi.py
# training_module.py

# Immediately add .env to .gitignore so keys are never committed
echo ".env" >> .gitignore
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

### 4. Environment Configuration

```bash
# Step 1 -- Generate the .env file from the built-in template
python3 -c "
from deployment_architecture import ENV_TEMPLATE
with open('.env', 'w') as f:
    f.write(ENV_TEMPLATE.strip())
print('.env created successfully')
"

# Step 2 -- Open and fill in your API keys
nano .env
# Or use your preferred editor: code .env / vim .env

# Minimum required fields to fill in:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
#   STRIPE_SECRET_KEY=sk_test_...
#   STRIPE_WEBHOOK_SECRET=whsec_...
#   SECRET_KEY=<generate below>

# Step 3 -- Generate a cryptographically secure SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
# Copy the output and paste it into your .env file

# Step 4 -- Verify no placeholder values remain
grep "YOUR_KEY_HERE" .env
# Expected: no output (zero matches)

# Step 5 -- Confirm .env is not tracked by git
git status .env
# Expected: .env should NOT appear (it is gitignored)

# Step 6 -- Quick sanity check on key format
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv()
openai_key = os.getenv('OPENAI_API_KEY', '')
anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
assert openai_key.startswith('sk-'), f'OpenAI key looks wrong: {openai_key[:10]}'
assert anthropic_key.startswith('sk-ant-'), f'Anthropic key looks wrong: {anthropic_key[:10]}'
print('✅ API key format validated')
"
```

---

### 5. Docker -- Local Development Setup

```bash
# Step 1 -- Generate all Docker and dependency files from deployment_architecture.py
python3 -c "
from deployment_architecture import DOCKER_COMPOSE, DOCKERFILE_API, REQUIREMENTS_TXT
with open('docker-compose.yml', 'w') as f: f.write(DOCKER_COMPOSE)
with open('Dockerfile.api', 'w') as f:     f.write(DOCKERFILE_API)
with open('Dockerfile.worker', 'w') as f:  f.write(DOCKERFILE_API)
with open('requirements.txt', 'w') as f:   f.write(REQUIREMENTS_TXT)
print('✅ docker-compose.yml')
print('✅ Dockerfile.api')
print('✅ Dockerfile.worker')
print('✅ requirements.txt')
"

# Step 2 -- Pull base images (PostgreSQL with pgvector, Redis)
docker compose pull

# Step 3 -- Build the API and Worker images
docker compose build
# This installs all Python dependencies -- takes 3–5 minutes on first run

# Step 4 -- Start all services in detached mode
docker compose up -d
# Services started: api * worker * scheduler * postgres * redis * flower

# Step 5 -- Confirm all containers are healthy
docker compose ps
# All services should show Status: healthy or running

# Step 6 -- Tail logs until you see the brain initialise
docker compose logs -f api
# Wait for the line: techit_ai_brain_ready  agents=21  services=16
# Press Ctrl+C to exit log tail

# Step 7 -- Quick smoke test
curl http://localhost:8000/health
# Expected: {"status":"healthy","ai_brain":"operational","version":"2.0.0","agents":21}
```

**Service ports:**

| Service | Port | URL |
|---------|------|-----|
| API | 8000 | http://localhost:8000 |
| Swagger docs | 8000 | http://localhost:8000/docs |
| Flower (Celery monitor) | 5555 | http://localhost:5555 |
| PostgreSQL | 5432 | `postgresql://techit:password@localhost:5432/techit_db` |
| Redis | 6379 | `redis://localhost:6379` |

---

### 6. Database Initialisation

```bash
# Step 1 -- Wait for PostgreSQL to be fully ready
docker compose exec postgres pg_isready -U techit
# Expected: /var/run/postgresql:5432 - accepting connections

# Step 2 -- Enable required PostgreSQL extensions
docker compose exec postgres psql -U techit -d techit_db -c "
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','uuid-ossp','pg_trgm');
"
# Expected: 3 rows showing each extension with its version

# Step 3 -- Initialise Alembic for migrations
docker compose exec api alembic init migrations

# Step 4 -- Configure Alembic to recognise TechIT's schema
# Edit migrations/env.py -- replace the target_metadata line:
docker compose exec api python3 -c "
content = open('migrations/env.py').read()
content = content.replace(
    'target_metadata = None',
    'from database_schema import Base\ntarget_metadata = Base.metadata'
)
open('migrations/env.py', 'w').write(content)
print('✅ migrations/env.py configured')
"

# Step 5 -- Generate the initial migration (detects all 30 tables)
docker compose exec api alembic revision --autogenerate -m "initial_techit_schema_v2"

# Step 6 -- Apply migrations (creates all 30 tables)
docker compose exec api alembic upgrade head

# Step 7 -- Verify tables were created
docker compose exec postgres psql -U techit -d techit_db -c "\dt" | grep -c "public"
# Expected: 30 or higher

# Step 8 -- Deploy SQL functions and live views
python3 -c "
from deployment_architecture import INIT_SQL
with open('init_functions.sql', 'w') as f:
    f.write(INIT_SQL)
print('init_functions.sql written')
"
docker compose exec -T postgres psql -U techit -d techit_db < init_functions.sql
# Expected output includes: CREATE FUNCTION × 3, CREATE VIEW × 3

# Step 9 -- Create pgvector indexes for semantic search performance
docker compose exec postgres psql -U techit -d techit_db -c "
CREATE INDEX IF NOT EXISTS idx_user_skill_vec
    ON user_skill_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_idea_vec
    ON idea_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
SELECT indexname FROM pg_indexes WHERE indexname LIKE 'idx_%_vec';
"
# Expected: 2 index names returned

# Step 10 -- Confirm schema is complete
docker compose exec postgres psql -U techit -d techit_db -c "
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
"
# Expected: 30 tables listed alphabetically
```

---

### 7. Verify All Services

Run these checks in order. Each should pass before moving to the next.

```bash
# ── Check 1: API health ────────────────────────────────────────────────────
curl -s http://localhost:8000/health | python3 -m json.tool
# Expected:
# {
#   "status": "healthy",
#   "ai_brain": "operational",
#   "version": "3.0.0",
#   "agents": 33,
#   "scoring_models": 20,
#   "task_types": 49,
#   "db_tables": 41
# }

# ── Check 2: All 18 scoring models ────────────────────────────────────────
docker compose exec api python3 -c "
from ai_router_core import ScoringEngine
import math

gsis = ScoringEngine.compute_gsis(70,65,60,55,40,72,50,35,80)
ups  = ScoringEngine.compute_unicorn_potential_score({k:8.0 for k in ScoringEngine.UNICORN_WEIGHTS})
evi_i = ScoringEngine.compute_evi_investor(85,87,94,85,81,80,3)
decay = ScoringEngine.compute_decay_factor(30)

print(f'GSIS:  {gsis[\"gsis\"]}  -- {gsis[\"classification\"]}')
print(f'UPS:   {ups[\"unicorn_potential_score\"]}%  -- {ups[\"classification\"]}')
print(f'EVI-I: {evi_i[\"adjusted_evi_i\"]}  (decay: {evi_i[\"decay_factor\"]})')
print(f'Decay(30d): {decay}  (expected: {round(math.exp(-0.02*30), 6)})')
assert 0 < gsis['gsis'] < 100
assert evi_i['adjusted_evi_i'] < evi_i['raw_evi_i']
assert abs(decay - round(math.exp(-0.02*30), 6)) < 1e-9
print('✅ All scoring models verified')
"

# ── Check 3: All 33 agents registered ─────────────────────────────────────
docker compose exec api python3 -c "
from agent_orchestration import AgentOrchestrator, AgentType
from ai_router_core import AICommandLayer, ModelRouter, PromptEngine, SafetyEngine
orch = AgentOrchestrator(AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine()))
assert len(orch.agents) == 33, f'Expected 33, got {len(orch.agents)}'
for at in AgentType:
    assert at in orch.agents, f'Missing: {at.value}'
print(f'✅ All {len(orch.agents)} agents registered')
for at, agent in orch.agents.items():
    print(f'   {agent.config.name}')
"

# ── Check 3b: All 20 scoring models ───────────────────────────────────────
docker compose exec api python3 -c "
from ai_router_core import ScoringEngine
from idea_solution_hub import ImpactScoringEngine
import math

# 18 existing models
gsis  = ScoringEngine.compute_gsis(70,65,60,55,40,72,50,35,80)
ups   = ScoringEngine.compute_unicorn_potential_score({k:8.0 for k in ScoringEngine.UNICORN_WEIGHTS})
evi_i = ScoringEngine.compute_evi_investor(85,87,94,85,81,80,3)
decay = ScoringEngine.compute_decay_factor(30)

# Models 19-20: Impact Score + Problem Priority Score
eng    = ImpactScoringEngine()
impact = eng.compute_impact_score(50.0, 8.5, 7.0, 6.5, 8.0)
from idea_solution_hub import ProblemUrgency
priority = eng.compute_priority_score(impact['impact_score'], ProblemUrgency.CRITICAL, 7.0, 6.0, 8.5)

print(f'GSIS:           {gsis["gsis"]}')
print(f'UPS:            {ups["unicorn_potential_score"]}%')
print(f'EVI-I:          {evi_i["adjusted_evi_i"]}')
print(f'Decay(30d):     {decay}')
print(f'Impact Score:   {impact["impact_score"]}  ({impact["classification"]})')
print(f'Priority Score: {priority["priority_score"]} {priority["colour"]}')
assert 0 < gsis['gsis'] < 100
assert evi_i['adjusted_evi_i'] < evi_i['raw_evi_i']
assert 0 < impact['impact_score'] < 100
assert priority['colour'] in ['🔴','🟠','🟡','🔵']
print('✅ All 20 scoring models verified')
"

# ── Check 3c: IP protection layer ─────────────────────────────────────────
docker compose exec api python3 -c "
from ai_router_core import SafetyEngine
from integration_guide import IPProtectionService, TechITAIBrain
from database_schema import RLS_POLICIES_SQL, apply_rls_policies

# Fingerprint + leak check
ip_svc = IPProtectionService(TechITAIBrain())
fp1 = ip_svc.fingerprint('AI telemedicine platform for rural access')
fp2 = ip_svc.fingerprint('AI telemedicine platform for rural access')
fp3 = ip_svc.fingerprint('completely different idea')
assert fp1 == fp2 and len(fp1) == 64 and fp1 != fp3

blocked = ip_svc.check_exact_match(fp1, [fp3, fp1])
allowed = ip_svc.check_exact_match(fp1, [fp3])
assert blocked['action'] == 'block'
assert allowed['action'] == 'allow'

# RLS policies exist and cover 9 tables
for t in ['projects','ai_outputs','idea_embeddings','generated_documents',
          'solution_projects','grant_applications','credit_ledger']:
    assert t in RLS_POLICIES_SQL

status = ip_svc.get_protection_status()
assert status['protection_layers']['row_level_security']['active'] is True

print('✅ IP Protection Layer verified:')
print(f'   SHA-256 fingerprinting:     operational')
print(f'   Exact-match leak detection: block on collision, allow on clear')
print(f'   RLS policies:               9 tables covered')
print(f'   techit_system bypass role:  IP detection only')
"

# ── Check 3d: Idea & Solution Hub ─────────────────────────────────────────
docker compose exec api python3 -c "
from idea_solution_hub import (ImpactScoringEngine, ProblemDiscoveryEngine,
    DeploymentEngine, SolutionProject, SolutionType, FundingType,
    SolutionStage, DeploymentMode, ContributorRole, ProblemUrgency)

# Impact + Priority scores
eng    = ImpactScoringEngine()
impact = eng.compute_impact_score(50.0, 8.5, 7.0, 6.5, 8.0)
prio   = eng.compute_priority_score(impact['impact_score'], ProblemUrgency.CRITICAL, 7.0, 6.0, 8.5)

# Discovery engine
disc  = ProblemDiscoveryEngine()
found = disc.discover(region='Africa', limit=2)
assert len(found) == 2

# Deployment engine
sol = SolutionProject(
    problem_id='p1', title='Cold Storage', solution_type=SolutionType.SOCIAL_INITIATIVE,
    funding_type=FundingType.GRANTS, stage=SolutionStage.VALIDATED,
    execution_plan='Phase 1 pilot', required_roles=[ContributorRole.FIELD_OPERATOR],
    impact_score=impact['impact_score'], feasibility_score=72.0,
)
dep  = DeploymentEngine()
plan = dep.create_deployment_plan(sol, DeploymentMode.NGO_ROLLOUT, 'West Africa', 5000)
assert len(plan.deployment_checklist) > 0

print(f'✅ Idea & Solution Hub verified:')
print(f'   Impact Score:    {impact["impact_score"]} -- {impact["classification"]}')
print(f'   Priority Score:  {prio["priority_score"]} {prio["colour"]}')
print(f'   Discovery:       {len(found)} problems found')
print(f'   Deployment plan: {len(plan.deployment_checklist)} checklist items')
"

# ── Check 3e: Document Generation Engine ──────────────────────────────────
docker compose exec api python3 -c "
from document_generation import (DocumentType, DocumentStyle, DocumentAudience,
    DocumentPromptEngine, ExportService, GeneratedDocument, ExportFormat)

prompt_e = DocumentPromptEngine()
for dt in DocumentType:
    schema = prompt_e.get_section_schema(dt)
    assert len(schema) > 0
    assert prompt_e.estimate_pages(dt, DocumentStyle.STANDARD) > 0

exp = ExportService()
link = exp.generate_shareable_link('doc_001', 30)
assert 'techit.io' in link

doc = GeneratedDocument(document_id='doc_001', document_type=DocumentType.PITCH_DECK,
    content='Test', word_count=500, page_estimate=12)
pdf = exp.export_to_pdf(doc)
assert pdf['ready'] is True

print('✅ Document Generation Engine verified:')
print(f'   8 document types with section schemas and page estimates')
print(f'   PDF export:      {pdf["url"]}')
print(f'   Shareable link:  {link}')
for dt in DocumentType:
    pages = prompt_e.estimate_pages(dt, DocumentStyle.STANDARD)
    print(f'   {dt.value}: {pages} pages (standard)')
"

# ── Check 4: Billing system ────────────────────────────────────────────────
docker compose exec api python3 -c "
from billing_system import ALL_PLANS, CREDIT_OPERATIONS, HybridCreditEngine, FOUNDER_BUILDER
from billing_system import UserBillingState, BillingRole
from datetime import datetime, timedelta
print(f'Plans registered:      {len(ALL_PLANS)}   (expected: 11)')
print(f'Operations registered: {len(CREDIT_OPERATIONS)}   (expected: 15)')
engine = HybridCreditEngine()
state = UserBillingState('test', BillingRole.FOUNDER, 'founder_builder', FOUNDER_BUILDER,
    1, datetime.utcnow()+timedelta(days=10), 20, 'monthly',
    datetime.utcnow()-timedelta(days=20), datetime.utcnow()+timedelta(days=10))
res = engine.resolve(state, 'unicorn_analysis')
assert res.approved and res.from_subscription == 1 and res.from_payg == 1
print(f'✅ Hybrid resolution: sub={res.from_subscription} PAYG={res.from_payg} USD=\${res.usd_cost_this_operation:.4f}')
"

# ── Check 5: Adaptive training module ─────────────────────────────────────
docker compose exec api python3 -c "
from training_module import ModuleLibrary, AdaptiveTrainingService
mods   = ModuleLibrary.all_modules()
svc    = AdaptiveTrainingService()
result = svc.generate_curriculum('test', 'founder', 'healthtech', 'idea', 8.0)
ls     = result['learning_summary']
print(f'Module library:       {len(mods)} canonical modules')
print(f'Estimated weeks:      {ls[\"estimated_weeks_to_mvp\"]} weeks to MVP')
print(f'Pre-MVP modules:      {result[\"pre_mvp\"][\"total_modules\"]}')
print(f'First module:         {result[\"next_module\"][\"title\"]}')
assert '12 weeks' not in str(result), 'Fixed week reference found -- should be dynamic'
print('✅ Adaptive training verified (no fixed week references)')
"

# ── Check 6: EVI-I investor signal ────────────────────────────────────────
docker compose exec api python3 -c "
from investor_evi import InvestorEVIService, EVIInvestorSignal
svc = InvestorEVIService()
result = svc.compute_from_startup({
    'project_id':'test','project_name':'HealthTech Co','industry':'Health',
    'stage':'beta','days_since_update':3,
    'milestones':{'committed_30d':8,'delivered_30d':7,'avg_days_complete':5.5,'late_count':1,'quality_score':8.2},
    'iteration':{'versions_30d':4,'feedback_fix_days':2.5,'feature_cycle_days':8.0,'pivots_90d':1},
    'response':{'investor_response_hrs':3.5,'collab_response_hrs':6.0,'sessions_per_week':9.0,'checkin_pct':95.0},
    'revenue':{'mrr_current':12500,'mrr_30d':9800,'mrr_90d':5200,'customers_now':47,'customers_30d':35,'arpu':265,'churn_pct':3.2},
    'users':{'users_now':820,'users_30d':610,'users_90d':310,'dau_wau':0.55,'week1_retention':52.0,'organic_pct':68.0},
    'capital':{'total_raised':250000,'monthly_burn':18000,'runway_months':14.0,'rev_per_dollar':0.60,'team_size':4,'rev_per_employee':37500},
}, previous_evi_i=65.0)
print(f'EVI-I Score:   {result.adjusted_evi_i}  ({result.signal_label} {result.signal_emoji})')
print(f'Decay factor:  {result.decay_factor}')
print(f'Trend:         {result.evi_trend}  ({result.trend_delta:+.1f} pts)')
print(f'Velocity risk: {result.velocity_risk}')
print(f'✅ EVI-I verified')
"

# ── Check 7: Celery workers ────────────────────────────────────────────────
docker compose exec worker celery -A workers.celery inspect registered
# Expected: lists all 14 registered tasks including:
#   daily_tour_guide, weekly_summaries, daily_investor_signals,
#   adaptive_curriculum_weekly, wcrs_gsis_refresh, stagnation_roster,
#   monthly_credit_reset, admin_anomaly_scan, investor_alert_check,
#   problem_discovery_daily, discussion_moderation_hourly,
#   deployment_status_refresh, document_cleanup_weekly, impact_snapshot_daily

# Check the Flower dashboard
echo "Open in browser: http://localhost:5555"
echo "All 14 scheduled tasks should appear under the 'Tasks' tab"
```

---

### 8. Running the API

```bash
# Start the API in development mode (auto-reload on file changes)
docker compose up api

# Or start all services together
docker compose up -d
docker compose logs -f api

# Access interactive API documentation
# Swagger UI:  http://localhost:8000/docs
# ReDoc:       http://localhost:8000/redoc

# Test a live endpoint -- daily check-in
curl -s -X POST http://localhost:8000/api/v1/tour-guide/daily-check-in \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_founder"}' | python3 -m json.tool

# Test idea diagnostic (1 credit, Free tier)
curl -s -X POST http://localhost:8000/api/v1/incubation/idea/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "startup_name": "MediConnect",
    "industry": "Healthtech",
    "problem": "Rural patients cannot access specialist doctors",
    "solution": "AI-powered telemedicine with remote triage"
  }' | python3 -m json.tool

# Test GSIS computation (1 credit)
curl -s -X POST http://localhost:8000/api/v1/gsis/compute \
  -H "Content-Type: application/json" \
  -d '{
    "pps": 65, "evi": 70, "mrs": 55, "bss": 50,
    "rgs": 30, "frs": 72, "cis": 45, "iis": 20, "cs": 80
  }' | python3 -m json.tool

# Run the API in production mode (no auto-reload, multiple workers)
docker compose -f docker-compose.yml up -d api
# Or directly with uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

### 9. Running Celery Workers

```bash
# Start all workers and the scheduler together (included in docker compose up -d)
docker compose up worker scheduler

# Monitor tasks in real time
open http://localhost:5555  # Flower dashboard

# Or via CLI
docker compose exec worker celery -A workers.celery inspect active
docker compose exec worker celery -A workers.celery inspect scheduled
docker compose exec worker celery -A workers.celery inspect reserved

# Trigger a scheduled task manually for testing
docker compose exec worker celery -A workers.celery call daily_tour_guide
docker compose exec worker celery -A workers.celery call wcrs_gsis_refresh

# View task history
docker compose exec worker celery -A workers.celery events

# Check beat scheduler is running all 9 jobs
docker compose exec scheduler celery -A workers.celery beat --dry-run
# Expected: lists all 9 cron entries with their next run times

# Scale workers up (for production load)
docker compose up -d --scale worker=4
```

---

### 10. Running Without Docker (Native Python)

Use this if you cannot run Docker or want a lighter development setup.

```bash
# Step 1 -- Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate           # Linux / macOS
# .venv\Scripts\activate            # Windows

# Step 2 -- Install Python dependencies
pip install --upgrade pip
python3 -c "
from deployment_architecture import REQUIREMENTS_TXT
with open('requirements.txt', 'w') as f:
    f.write(REQUIREMENTS_TXT)
"
pip install -r requirements.txt

# Step 3 -- Install and start PostgreSQL with pgvector
# Ubuntu / Debian:
sudo apt-get install postgresql-16
sudo apt-get install postgresql-16-pgvector
sudo systemctl start postgresql
sudo -u postgres createdb techit_db
sudo -u postgres createuser techit --password  # set password: password

# macOS with Homebrew:
brew install postgresql@16
brew install pgvector
brew services start postgresql@16
createdb techit_db

# Step 4 -- Install and start Redis
# Ubuntu:
sudo apt-get install redis-server
sudo systemctl start redis

# macOS:
brew install redis
brew services start redis

# Step 5 -- Set environment variables directly
export DATABASE_URL="postgresql://techit:password@localhost:5432/techit_db"
export REDIS_URL="redis://localhost:6379"
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export ENVIRONMENT="development"

# Step 6 -- Run migrations
python3 -c "
from deployment_architecture import INIT_SQL
with open('init_functions.sql', 'w') as f:
    f.write(INIT_SQL)
"
alembic upgrade head
psql -U techit -d techit_db < init_functions.sql

# Step 7 -- Start the API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Step 8 -- Start Celery workers (separate terminal)
celery -A workers.celery worker --loglevel=info -Q default,ai_heavy,ai_light,scheduled

# Step 9 -- Start Celery Beat scheduler (separate terminal)
celery -A workers.celery beat --loglevel=info
```

---

### 11. Seeding the AI Prompt Registry

All AI system prompts live in the `ai_prompts` database table -- not in code. Seed them after running migrations.

```bash
# Step 1 -- Generate the SQL seed file from the PromptEngine registry
docker compose exec api python3 -c "
from ai_router_core import PromptEngine, TaskType

engine = PromptEngine()
inserts = []
credit_map = {
    'unicorn_analysis': 2, 'market_intelligence': 2, 'business_plan': 4,
    'startup_strategy': 3, 'finance_strategy': 2, 'investor_readiness': 2,
    'executive_summary': 2, 'market_survey_simulation': 3, 'tech_stack_design': 2,
    'investor_evi': 2, 'risk_analysis': 2, 'investor_signal': 2,
}

for task_type, prompt in engine.SYSTEM_PROMPTS.items():
    safe   = prompt.replace(\"'\", \"''\")
    credit = credit_map.get(task_type.value, 1)
    inserts.append(f'''
INSERT INTO ai_prompts (
    id, name, prompt_type, target_role, min_tier,
    system_prompt, user_prompt_template, version, is_active, credit_cost
) VALUES (
    uuid_generate_v4(), '{task_type.value}_v1', '{task_type.value}',
    'founder', 'free', '{safe}',
    'USER CONTEXT:\n{{user}}\n\nTASK INPUT:\n{{input}}',
    1, true, {credit}
) ON CONFLICT DO NOTHING;''')

sql = '\n'.join(inserts)
with open('/tmp/seed_prompts.sql', 'w') as f:
    f.write(sql)
print(f'Generated {len(inserts)} prompt inserts -> /tmp/seed_prompts.sql')
"

# Step 2 -- Execute the seed SQL
docker compose exec -T postgres psql -U techit -d techit_db < /tmp/seed_prompts.sql

# Step 3 -- Verify prompts were inserted
docker compose exec postgres psql -U techit -d techit_db -c "
SELECT name, prompt_type, credit_cost, is_active
FROM ai_prompts
ORDER BY name;
"
# Expected: one row per TaskType that has a system prompt defined

# Step 4 -- Verify prompt count
docker compose exec postgres psql -U techit -d techit_db -c "
SELECT COUNT(*) as total_prompts FROM ai_prompts WHERE is_active = true;
"
# Expected: 20+ rows
```

---

### 12. Pinecone Vector Store Setup (Optional)

By default TechIT uses **pgvector** for all embedding operations. Pinecone is optional and recommended only when your project count exceeds 50,000 (where pgvector IVFFlat indexes may degrade).

```bash
# Step 1 -- Create a Pinecone index
# Go to app.pinecone.io -> Create Index:
#   Name:       techit-embeddings
#   Dimensions: 1536   (OpenAI text-embedding-3-small output size)
#   Metric:     cosine
#   Pod type:   p1.x1  (starter) or s1.x1  (serverless)

# Step 2 -- Add Pinecone credentials to .env
echo "PINECONE_API_KEY=your-key-here" >> .env
echo "PINECONE_INDEX=techit-embeddings" >> .env
echo "PINECONE_ENV=us-east-1-aws" >> .env

# Step 3 -- Verify Pinecone connection
docker compose exec api python3 -c "
import os
from pinecone import Pinecone
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index(os.getenv('PINECONE_INDEX', 'techit-embeddings'))
stats = index.describe_index_stats()
print(f'✅ Pinecone connected')
print(f'   Index:      {os.getenv(\"PINECONE_INDEX\")}')
print(f'   Dimensions: {stats.dimension}')
print(f'   Vectors:    {stats.total_vector_count}')
"

# Step 4 -- The MatchingAgent and idea similarity search will automatically
# use Pinecone when PINECONE_API_KEY is set in the environment.
# No code changes required -- the routing is handled by the embedding layer.
```

---

### 13. Voice / Audio Setup (Optional)

ElevenLabs provides voice narration for Tour Guide daily briefings and training module audio.

```bash
# Step 1 -- Add ElevenLabs credentials to .env
echo "ELEVENLABS_API_KEY=your-key-here" >> .env

# Step 2 -- Verify connection and list available voices
docker compose exec api python3 -c "
import os, requests
headers = {'xi-api-key': os.getenv('ELEVENLABS_API_KEY')}
resp = requests.get('https://api.elevenlabs.io/v1/voices', headers=headers)
resp.raise_for_status()
voices = resp.json()['voices']
print(f'✅ ElevenLabs connected -- {len(voices)} voices available')
for v in voices[:5]:
    print(f'   {v[\"voice_id\"]}  {v[\"name\"]}')
"

# Step 3 -- Test audio generation for Tour Guide
docker compose exec api python3 -c "
import os, requests
headers = {
    'xi-api-key': os.getenv('ELEVENLABS_API_KEY'),
    'Content-Type': 'application/json'
}
# Use the first available voice
resp = requests.get('https://api.elevenlabs.io/v1/voices', headers=headers)
voice_id = resp.json()['voices'][0]['voice_id']

audio_resp = requests.post(
    f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
    headers=headers,
    json={'text': 'TechIT AI Tour Guide is active. Your momentum score is 72.', 'model_id': 'eleven_monolingual_v1'}
)
audio_resp.raise_for_status()
with open('/tmp/test_briefing.mp3', 'wb') as f:
    f.write(audio_resp.content)
print(f'✅ Audio generated: {len(audio_resp.content):,} bytes -> /tmp/test_briefing.mp3')
"

# Step 4 -- Add S3 bucket for audio storage (recommended for production)
# Add to .env:
#   AWS_ACCESS_KEY_ID=...
#   AWS_SECRET_ACCESS_KEY=...
#   AWS_REGION=us-east-1
#   AWS_S3_BUCKET=techit-assets
# Audio files will be uploaded to S3 and their URLs stored in ai_audio_outputs table
```

---

### 14. Running Tests

```bash
# ── Full integration test suite ────────────────────────────────────────────
docker compose exec api python3 -c "
import asyncio, math

print('=' * 60)
print('TECHIT INTEGRATION TEST SUITE')
print('=' * 60)

# 1. All 18 scoring models
from ai_router_core import ScoringEngine, CreditCost, TaskType, SubscriptionTier, SubscriptionAccessControl
gsis  = ScoringEngine.compute_gsis(70,65,60,55,40,72,50,35,80)
ups   = ScoringEngine.compute_unicorn_potential_score({k:8.0 for k in ScoringEngine.UNICORN_WEIGHTS})
evi_i = ScoringEngine.compute_evi_investor(85,87,94,85,81,80,3)
for name, val in [('GSIS',gsis['gsis']),('UPS',ups['unicorn_potential_score']),('EVI-I',evi_i['adjusted_evi_i'])]:
    assert 0 < val < 100, f'{name} out of range: {val}'
assert ScoringEngine.compute_decay_factor(0) == 1.0
assert CreditCost.cost_for(TaskType.BUSINESS_PLAN) == 4
assert CreditCost.cost_for(TaskType.TOUR_GUIDE) == 0
assert SubscriptionAccessControl.is_allowed(SubscriptionTier.FREE, TaskType.TRAINING_GENERATION)
assert not SubscriptionAccessControl.is_allowed(SubscriptionTier.FREE, TaskType.BUSINESS_PLAN)
print('✅ [1/7] ai_router_core -- 18 models, credit economy, access control')

# 2. Billing -- hybrid resolution
from billing_system import HybridCreditEngine, UserBillingState, BillingRole, FOUNDER_BUILDER, FOUNDER_FREE
from billing_system import PaywallEnforcementService, ReferralEngine, RevenueProjectionModel, ALL_PLANS
from datetime import datetime, timedelta
def st(pid, spec, sub, payg):
    return UserBillingState('t',BillingRole.FOUNDER,pid,spec,sub,datetime.utcnow()+timedelta(days=10),payg,'monthly',datetime.utcnow()-timedelta(days=20),datetime.utcnow()+timedelta(days=10))
engine = HybridCreditEngine()
r = engine.resolve(st('founder_builder',FOUNDER_BUILDER,1,20),'unicorn_analysis')
assert r.approved and r.from_subscription==1 and r.from_payg==1
assert not engine.resolve(st('founder_free',FOUNDER_FREE,5,0),'business_plan').approved
proj = RevenueProjectionModel().project_90_day()
assert proj['total_paying'] == 178_500 and proj['mrr_usd'] == 15_712_500
print('✅ [2/7] billing_system -- hybrid resolution, paywall, revenue model')

# 3. EVI-I
from investor_evi import InvestorEVIService, EVIInvestorSignal
svc = InvestorEVIService()
r_strong = svc.compute_from_startup({'project_id':'p1','project_name':'Test','industry':'H','stage':'beta','days_since_update':3,'milestones':{'committed_30d':8,'delivered_30d':7,'avg_days_complete':5.5,'late_count':1,'quality_score':8.2},'iteration':{'versions_30d':4,'feedback_fix_days':2.5,'feature_cycle_days':8.0,'pivots_90d':1},'response':{'investor_response_hrs':3.5,'collab_response_hrs':6.0,'sessions_per_week':9.0,'checkin_pct':95.0},'revenue':{'mrr_current':12500,'mrr_30d':9800,'mrr_90d':5200,'customers_now':47,'customers_30d':35,'arpu':265,'churn_pct':3.2},'users':{'users_now':820,'users_30d':610,'users_90d':310,'dau_wau':0.55,'week1_retention':52.0,'organic_pct':68.0},'capital':{'total_raised':250000,'monthly_burn':18000,'runway_months':14.0,'rev_per_dollar':0.60,'team_size':4,'rev_per_employee':37500}},previous_evi_i=65.0)
assert r_strong.signal == EVIInvestorSignal.STRONG and r_strong.evi_trend == 'accelerating'
print(f'✅ [3/7] investor_evi -- EVI-I={r_strong.adjusted_evi_i} trend={r_strong.evi_trend}')

# 4. Adaptive training
from training_module import ModuleLibrary, AdaptiveTrainingService
mods = ModuleLibrary.all_modules()
res = AdaptiveTrainingService().generate_curriculum('u1','founder','health','idea',8.0)
assert res['learning_summary']['estimated_weeks_to_mvp'] > 0
assert '12 weeks' not in str(res)
assert res['next_module']['module_id'] == 'fv_001'
print(f'✅ [4/7] training_module -- {len(mods)} modules, {res[\"learning_summary\"][\"estimated_weeks_to_mvp\"]}wk to MVP (dynamic)')

# 5. Database schema
from database_schema import Base, REFERENCE_QUERIES
tables = {t.name for t in Base.metadata.tables.values()}
assert len(tables) >= 30 and len(REFERENCE_QUERIES) >= 7
print(f'✅ [5/7] database_schema -- {len(tables)} tables, {len(REFERENCE_QUERIES)} reference queries')

# 6. All 21 agents + event routing
from agent_orchestration import AgentOrchestrator, AgentType
from ai_router_core import AICommandLayer, ModelRouter, PromptEngine, SafetyEngine, UserContext, UserRole
orch = AgentOrchestrator(AICommandLayer(ModelRouter(),PromptEngine(),SafetyEngine()))
assert len(orch.agents) == 21
uc = UserContext('f1',UserRole.FOUNDER,SubscriptionTier.FOUNDER_PRO,150,'p1','idea','h',[],[],{'completion_percentage':0},0,0,days_since_update=0,team_size=2)
async def test_routing():
    for etype, expected in [('idea_submitted',3),('user_login',3),('milestone_updated',3)]:
        results = await orch.handle_event({'type':etype,'user_context':uc,'idea':{'title':'T','industry':'h','problem':'P','solution':'S'},'criteria':{}})
        assert len(results) == expected, f'{etype}: {len(results)} != {expected}'
asyncio.run(test_routing())
print(f'✅ [6/7] agent_orchestration -- 21 agents, event routing verified')

# 7. Integration guide
from integration_guide import TechITAIBrain, GSISService
brain = TechITAIBrain()
assert brain is TechITAIBrain()
gsis_val = GSISService(brain).compute({'pps':65,'evi':70,'mrs':60,'bss':55,'rgs':40,'frs':72,'cis':50,'iis':35,'cs':80})
assert 0 < gsis_val['gsis'] < 100
print(f'✅ [7/7] integration_guide -- singleton, GSIS={gsis_val[\"gsis\"]}')

print()
print('=' * 60)
print('✅ ALL 7 MODULES VERIFIED -- ZERO FAILURES')
print('=' * 60)
"

# ── Individual module tests ────────────────────────────────────────────────
# Run specific module tests during development:
docker compose exec api python3 -c "from ai_router_core import ScoringEngine; print(ScoringEngine.compute_gsis(70,65,60,55,40,72,50,35,80))"
docker compose exec api python3 -c "from billing_system import RevenueProjectionModel; print(RevenueProjectionModel().project_90_day()['mrr_usd'])"
docker compose exec api python3 -c "from training_module import ModuleLibrary; print(len(ModuleLibrary.all_modules()), 'modules')"
```

---

### 15. Production Deployment -- AWS

```bash
# ── Infrastructure provisioning (Terraform or AWS Console) ────────────────

# RDS PostgreSQL with pgvector
# - Engine:          PostgreSQL 16.x
# - Instance class:  db.r7g.large (production) / db.t3.medium (staging)
# - Storage:         100 GB gp3, auto-scaling enabled
# - Extensions:      vector, uuid-ossp, pg_trgm (enable after creation)
# - Multi-AZ:        Yes (production), No (staging)
# - Parameter group: max_connections=500, shared_preload_libraries='pg_stat_statements'

# ElastiCache Redis
# - Engine:          Redis 7.x
# - Node type:       cache.r7g.medium (production) / cache.t3.micro (staging)
# - Cluster mode:    Disabled (single shard is sufficient)
# - Auth token:      Enabled

# S3 Bucket for audio/documents
aws s3 mb s3://techit-assets-prod --region us-east-1
aws s3api put-bucket-versioning --bucket techit-assets-prod --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket techit-assets-prod --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ── Secrets Manager (NEVER use .env files in production) ──────────────────
# Store all secrets in AWS Secrets Manager:
aws secretsmanager create-secret --name techit/prod/openai_api_key \
    --secret-string '{"OPENAI_API_KEY":"sk-..."}'

aws secretsmanager create-secret --name techit/prod/anthropic_api_key \
    --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-..."}'

aws secretsmanager create-secret --name techit/prod/stripe_keys \
    --secret-string '{"STRIPE_SECRET_KEY":"sk_live_...","STRIPE_WEBHOOK_SECRET":"whsec_..."}'

aws secretsmanager create-secret --name techit/prod/database_url \
    --secret-string '{"DATABASE_URL":"postgresql://techit:STRONG_PASSWORD@rds-endpoint:5432/techit_db"}'

# ── ECS Task Definition ────────────────────────────────────────────────────
# Push Docker image to ECR:
aws ecr create-repository --repository-name techit-api
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t techit-api .
docker tag techit-api:latest <account>.dkr.ecr.<region>.amazonaws.com/techit-api:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/techit-api:latest

# ── ALB Health Check ───────────────────────────────────────────────────────
# Target group health check:
#   Protocol: HTTP
#   Path:     /health
#   Matcher:  200
#   Interval: 30s
#   Threshold: 2 healthy, 3 unhealthy

# ── Auto Scaling ───────────────────────────────────────────────────────────
# API service: min=3, max=20, scale on CPU > 70%
# Worker service: min=2, max=8, scale on SQS queue depth > 100
```

---

### 16. Production Deployment -- Kubernetes

```bash
# Step 1 -- Generate the Kubernetes manifest from deployment_architecture.py
python3 -c "
from deployment_architecture import K8S_MANIFEST
with open('k8s-techit.yaml', 'w') as f:
    f.write(K8S_MANIFEST)
print('k8s-techit.yaml written')
"

# Step 2 -- Create the namespace
kubectl create namespace techit-prod

# Step 3 -- Create secrets (from AWS Secrets Manager or manually)
kubectl create secret generic techit-secrets \
    --from-literal=database-url="postgresql://techit:pass@postgres:5432/techit_db" \
    --from-literal=openai-api-key="sk-..." \
    --from-literal=anthropic-api-key="sk-ant-..." \
    --from-literal=stripe-secret-key="sk_live_..." \
    --from-literal=redis-url="redis://redis:6379" \
    --namespace techit-prod

# Step 4 -- Deploy PostgreSQL with pgvector (or use external RDS)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install techit-postgres bitnami/postgresql \
    --namespace techit-prod \
    --set image.tag=16 \
    --set primary.extraEnvVars[0].name=POSTGRESQL_SHARED_PRELOAD_LIBRARIES \
    --set primary.extraEnvVars[0].value=pg_stat_statements

# Step 5 -- Deploy Redis
helm install techit-redis bitnami/redis \
    --namespace techit-prod \
    --set architecture=standalone

# Step 6 -- Apply the TechIT manifests
kubectl apply -f k8s-techit.yaml --namespace techit-prod

# Step 7 -- Watch rollout
kubectl rollout status deployment/techit-api --namespace techit-prod

# Step 8 -- Verify all pods are running
kubectl get pods --namespace techit-prod
# Expected: api (3 replicas), worker (2 replicas), scheduler (1 replica)

# Step 9 -- View logs
kubectl logs -l app=techit-api --namespace techit-prod --tail=50 -f

# Step 10 -- Get the external IP
kubectl get service techit-api --namespace techit-prod
# Copy the EXTERNAL-IP -- this is your load balancer address

# Useful commands:
kubectl describe pod <pod-name> --namespace techit-prod   # Diagnose issues
kubectl exec -it <pod-name> --namespace techit-prod -- /bin/sh  # Shell into pod
kubectl scale deployment techit-api --replicas=6 --namespace techit-prod  # Manual scale
```

---

### 17. CI/CD Pipeline -- GitHub Actions

Create `.github/workflows/deploy.yml` in your repository:

```yaml
name: TechIT -- Build, Test, Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/techit-api

jobs:

  test:
    name: Run Integration Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: techit
          POSTGRES_PASSWORD: password
          POSTGRES_DB: techit_db
        ports:
          - 5432:5432
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: --health-cmd "redis-cli ping" --health-interval 10s

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run database migrations
        env:
          DATABASE_URL: postgresql://techit:password@localhost:5432/techit_db
        run: |
          alembic upgrade head
          python3 -c "
          from deployment_architecture import INIT_SQL
          with open('init_functions.sql', 'w') as f: f.write(INIT_SQL)
          "
          psql postgresql://techit:password@localhost:5432/techit_db < init_functions.sql

      - name: Run integration test suite
        env:
          DATABASE_URL: postgresql://techit:password@localhost:5432/techit_db
          REDIS_URL: redis://localhost:6379
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SECRET_KEY: test-secret-key-for-ci-only
        run: |
          python3 -c "
          from ai_router_core import ScoringEngine, SubscriptionTier, SubscriptionAccessControl, TaskType
          gsis = ScoringEngine.compute_gsis(70,65,60,55,40,72,50,35,80)
          assert 0 < gsis['gsis'] < 100
          assert SubscriptionAccessControl.is_allowed(SubscriptionTier.FREE, TaskType.TRAINING_GENERATION)
          from billing_system import RevenueProjectionModel, ALL_PLANS, CREDIT_OPERATIONS
          assert len(ALL_PLANS) == 11 and len(CREDIT_OPERATIONS) == 15
          from training_module import ModuleLibrary
          assert len(ModuleLibrary.all_modules()) == 35
          from database_schema import Base
          assert len(Base.metadata.tables) >= 30
          print('✅ All CI tests passed')
          "

  build-and-push:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.api
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Kubernetes
        uses: azure/k8s-deploy@v4
        with:
          namespace: techit-prod
          manifests: k8s-techit.yaml
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Verify deployment health
        run: |
          sleep 30
          curl -f https://api.techit.io/health
          echo "✅ Production deployment healthy"
```

---

### 18. Monitoring Setup

```bash
# ── Sentry (error tracking) ────────────────────────────────────────────────
# 1. Create a project at sentry.io -> Python -> FastAPI
# 2. Copy the DSN (looks like: https://abc123@o123.ingest.sentry.io/456)
# 3. Add to .env:
echo "SENTRY_DSN=https://your-dsn@sentry.io/project-id" >> .env

# Verify Sentry is receiving events
docker compose exec api python3 -c "
import sentry_sdk
import os
sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'))
sentry_sdk.capture_message('TechIT platform health check -- Sentry connected')
print('✅ Test event sent to Sentry -- check your Sentry dashboard')
"

# ── Prometheus + Grafana (metrics) ─────────────────────────────────────────
# Add to docker-compose.yml or run separately:
docker run -d --name prometheus -p 9090:9090 \
    -v ./prometheus.yml:/etc/prometheus/prometheus.yml \
    prom/prometheus

docker run -d --name grafana -p 3001:3000 \
    -e GF_SECURITY_ADMIN_PASSWORD=admin \
    grafana/grafana

# Metrics exposed at: http://localhost:8000/metrics
# Key dashboards to create:
#   - GSIS score distribution across all projects
#   - AI cost per user per day (from credit_ledger)
#   - Agent execution success rates by agent_type
#   - Paywall conversion rates by operation_id
#   - EVI-I distribution across active startups
#   - Decay factor histogram (stagnation risk)
#   - Credit burn rate by subscription tier

# ── CloudWatch Alerts (AWS production) ────────────────────────────────────
# Configure alerts for:
aws cloudwatch put-metric-alarm \
    --alarm-name "TechIT-API-HighErrorRate" \
    --alarm-description "API 5xx error rate above 5%" \
    --metric-name "5XXError" --namespace "AWS/ApplicationELB" \
    --statistic Average --period 300 --threshold 0.05 \
    --comparison-operator GreaterThanThreshold \
    --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:techit-alerts

# Additional alerts to configure in your monitoring platform:
# ALERT: Monthly AI cost per user exceeds $10
#   Query: SELECT user_id, SUM(cost) FROM ai_outputs
#          WHERE created_at > date_trunc('month', NOW())
#          GROUP BY user_id HAVING SUM(cost) > 10

# ALERT: Single request cost exceeds $0.50
#   Query: SELECT * FROM ai_outputs WHERE cost > 0.50

# ALERT: Agent failure rate > 10% (last 1 hour)
#   Query: SELECT agent_type, 1 - (SUM(CASE WHEN success THEN 1 END)::float / COUNT(*))
#          FROM agent_execution_logs WHERE started_at > NOW() - INTERVAL '1 hour'
#          GROUP BY agent_type HAVING above_threshold

# ALERT: > 20% of active projects have decay_factor < 0.70 (stagnation)
#   Query: SELECT COUNT(*) FROM projects WHERE decay_factor < 0.70

# ALERT: Celery queue depth > 500 (workers overwhelmed)
#   Monitor via Redis: LLEN celery (default queue length)

# Flower (Celery monitoring) -- already running at http://localhost:5555
# For production, secure with basic auth:
docker compose exec scheduler celery -A workers.celery flower \
    --basic_auth=admin:your-secure-password \
    --port=5555
```

---

### 19. Common Errors and Fixes

**`ModuleNotFoundError: No module named 'sqlalchemy'`**
```bash
pip install sqlalchemy==2.0.31 psycopg2-binary pgvector
# Or inside Docker:
docker compose exec api pip install sqlalchemy psycopg2-binary pgvector
```

**`PermissionError: Request blocked: Requires builder plan.`**
The user's `subscription_tier` does not have access to the requested `TaskType`. Check `SubscriptionAccessControl.TIER_MAP` in `ai_router_core.py`. Either upgrade the user's tier or verify the operation is appropriate for their plan.

**`TypeError: Object of type UserContext is not JSON serializable`**
This was a known bug -- fixed in the current version. Ensure you are running the latest `ai_router_core.py`. The `SafetyEngine` and `PromptEngine` both use `default=str` in `json.dumps`.

**`alembic.util.exc.CommandError: Target database is not up to date`**
```bash
docker compose exec api alembic current     # See current revision
docker compose exec api alembic history     # See migration history
docker compose exec api alembic upgrade head # Apply all pending migrations
```

**`psycopg2.errors.UndefinedFunction: function vector(...) does not exist`**
The pgvector extension was not created. Run:
```bash
docker compose exec postgres psql -U techit -d techit_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**`redis.exceptions.ConnectionError: Error connecting to Redis`**
```bash
docker compose ps redis          # Check Redis container is running
docker compose restart redis     # Restart if unhealthy
redis-cli -h localhost ping      # Should return: PONG
```

**`celery.exceptions.NotRegistered: daily_tour_guide`**
The worker has not imported the task module. Ensure `workers/celery.py` imports the task file and run:
```bash
docker compose restart worker scheduler
docker compose exec worker celery -A workers.celery inspect registered
```

**`stripe.error.SignatureVerificationError`**
The `STRIPE_WEBHOOK_SECRET` in `.env` does not match the webhook signing secret in your Stripe dashboard. Update it and restart the API.

**Decay factor not updating (scores not decreasing for inactive projects)**
The `wcrs_gsis_refresh` Celery task runs every 30 minutes. Verify it is running:
```bash
docker compose exec worker celery -A workers.celery inspect scheduled
# Should show wcrs_gsis_refresh in the scheduled tasks list
```

**Port 8000 already in use**
```bash
lsof -i :8000          # Find what is using the port
kill -9 <PID>          # Kill it
docker compose up api  # Restart
```

**`PermissionError: Request blocked: Prompt injection detected.`**
User input contains one of the 13 injection patterns monitored by `SafetyEngine._detect_injection()`. Common false positives: the phrase "act as" in a legitimate business context. To add a whitelist, extend `SafetyEngine.INJECTION_PATTERNS` in `ai_router_core.py` -- remove the specific pattern or add pre-processing to escape it before the AI call.

**`AssertionError: ip_protected=True required for this TaskType`**
An AI call that handles proprietary idea or solution content was made without `ip_protected=True`. Check the call site and add `ip_protected=True` to the `AIRequest`. All operations on `IDEA_EVALUATION`, `UNICORN_ANALYSIS`, `BUSINESS_PLAN`, `EXECUTIVE_SUMMARY`, `PIVOT_INTELLIGENCE`, `RISK_ANALYSIS`, `SOLUTION_SYNTHESIS`, `DEPLOYMENT_PLANNING`, `GRANT_MATCHING`, `FEASIBILITY_ESTIMATE`, and all `DOCUMENT_*` types must set `ip_protected=True`.

**RLS policy blocks a query that should be allowed (`policy violation` in psycopg2)**
The application is connecting without setting `app.user_id`:
```python
# Add to FastAPI middleware or DB session setup:
conn.execute("SET app.user_id = %s", [str(current_user.id)])
conn.execute("SET app.user_role = %s", [current_user.role.value])
```
For admin/scheduled Celery tasks that need to bypass RLS, connect as `techit_system` role -- **not** as `techit_app`.

**`idea_embeddings` table is empty -- leak detection not firing**
The embedding creation call in `VentureIntakeAgent` and `IdeaSolutionHubService.submit_problem()` is currently a stub. To activate it in production:
1. Uncomment the `TaskType.EMBEDDINGS` call in `VentureIntakeAgent.execute()`
2. Add the SQLAlchemy `INSERT INTO idea_embeddings` statement
3. Run `apply_rls_policies(engine)` from `database_schema.py` to enable row-level isolation
4. Verify with: `SELECT COUNT(*) FROM idea_embeddings;` -- should grow with each new idea submission

**Document generation returns `credits_consumed: 0`**
The `AIRequest` in `DocumentGenerationService.generate_document()` uses `ip_protected=True` but the mock `_call_llm` returns a placeholder response with no credit deduction. In production, ensure your `AICommandLayer._call_llm()` connects to the real OpenAI/Anthropic API and returns the actual token count for `CreditCost` to deduct correctly.

**`ImpactScore` returns 0.0 for all inputs**
Check that `people_affected_millions` is passed as a float greater than 0. The log-normalisation in `ImpactScoringEngine.compute_impact_score()` returns `pa_score = 0.0` only when `people_affected_millions <= 0`. Example fix:
```python
impact = eng.compute_impact_score(
    people_affected_millions=1.5,  # not 0
    severity=7.0, scalability=6.0, sustainability=6.0, measurability=7.0
)
```

---

### 20. Post-Installation Checklist

Run through every item before considering the setup complete.

```
INFRASTRUCTURE
  □ All Docker containers show Status: healthy  (docker compose ps)
  □ PostgreSQL 16 running with pgvector extension active
  □ Redis 7 running and responding to PING
  □ Flower dashboard accessible at http://localhost:5555

DATABASE
  □ All 41 tables created  (docker compose exec postgres psql -U techit -d techit_db -c "\dt" | wc -l)
  □ Extensions installed: vector, uuid-ossp, pg_trgm
  □ SQL functions deployed: top_startups, find_similar_ideas, find_skill_matches
  □ Live views created: project_scores_live, monthly_credit_burn, stagnating_projects
  □ pgvector indexes created: idx_user_skill_vec, idx_idea_vec
  □ ai_prompts table seeded (20+ rows)
  □ Idea & Solution Hub tables present: problem_nodes, solution_projects,
      discussion_threads, discussion_contributions, solution_deployments,
      field_feedback, impact_snapshots, grant_applications
  □ Document Generation tables present: generated_documents,
      document_exports, document_templates
  □ RLS policies applied: apply_rls_policies(engine) called post-migration
  □ techit_app role created (non-superuser -- RLS always enforced)
  □ techit_system role created (BYPASSRLS -- IP leak detection only)

API
  □ GET /health returns {"status":"healthy","agents":33,"scoring_models":20,"task_types":49}
  □ Swagger UI accessible at http://localhost:8000/docs
  □ POST /api/v1/tour-guide/daily-check-in returns momentum score
  □ POST /api/v1/gsis/compute returns a valid GSIS score
  □ POST /api/v1/training/curriculum/generate returns adaptive curriculum (not "12 weeks")
  □ POST /api/v1/solutions/problems/submit returns impact_score + priority_score + ip_fingerprint
  □ GET  /api/v1/solutions/impact/global returns headline metrics
  □ GET  /api/v1/documents/templates returns all 8 document types with credit costs
  □ POST /api/v1/documents/generate returns content + shareable_link + export URLs
  □ GET  /api/v1/ip-protection/status returns all 3 protection layers as active

SCORING ENGINE
  □ GSIS returns value in [0, 100]
  □ EVI-I returns adjusted score < raw score (decay applied)
  □ Decay factor for 0 days = 1.0 exactly
  □ Unicorn score at all-8.0 drivers = 80.0 exactly
  □ ImpactScore for 50M people, severity=8.5 returns value in (70, 90)
  □ ProblemPriorityScore for CRITICAL urgency returns colour in 🔴🟠🟡🔵

AGENTS
  □ All 33 agents registered in orchestrator
  □ idea_submitted event triggers 3 agents: VentureIntake + RiskEvaluator + Matching
  □ user_login event triggers 3 agents: TourGuide + Dashboard + GSISCompute
  □ revenue_went_live triggers 2 agents (system investor context elevation works)
  □ problem_submitted triggers 2 agents: ProblemAnalyzer + SolutionMatcher
  □ solution_converted triggers 3 agents: SolutionSynthesizer + ImpactPredictor + FeasibilityEstimator
  □ deployment_created triggers 1 agent: DeploymentPlanner
  □ document_requested triggers 1 agent: DocumentGeneration

BILLING
  □ 11 plans registered, 15 credit operations registered
  □ Hybrid resolution: subscription credits deducted first, PAYG as overflow
  □ Paywall fires correctly for Free user attempting business_plan operation
  □ Referral engine: invite_collaborator returns 5 credits reward
  □ Document Generation credit costs: exec_summary=2, pitch_deck=3, business_plan=4
  □ Idea Hub credit costs: problem_analysis=2, solution_synthesis=3, grant_matching=3

TRAINING
  □ 35 canonical modules in library (20 pre-MVP, 15 post-MVP)
  □ Time-to-MVP returns > 15 weeks for solo non-technical founder at idea stage
  □ Intensive technical team returns < 5 weeks
  □ No "12 weeks" string appears in any generated curriculum
  □ Post-MVP all-5-tracks unlock when: stage=growth, revenue=true, investor_interest=true

IP PROTECTION
  □ SHA-256 fingerprinting: every ip_protected=True AIRequest stamped before AI call
  □ Fingerprint stored in ai_outputs.input_data["_ip_fingerprint"]
  □ VentureIntakeAgent stores idea_fingerprint in shared_memory on every intake
  □ IdeaSolutionHubService.submit_problem() returns ip_fingerprint in response
  □ SafetyEngine.check_similarity_leak() blocks on exact fingerprint collision
  □ idea_embeddings table receives new rows on every idea submission (production)
  □ RLS policy project_owner_policy active on projects table
  □ RLS policy ai_output_owner_policy active on ai_outputs table
  □ RLS policy idea_embedding_owner_policy active on idea_embeddings table
  □ Investor visibility exception: surfaces score/stage only -- never idea_text
  □ IPProtectionService.get_protection_status() returns all 3 layers active=True

IDEA & SOLUTION HUB
  □ ImpactScoringEngine.compute_impact_score() returns 0.0 for all-zero inputs
  □ ImpactScoringEngine.compute_impact_score() returns > 90 for max inputs
  □ ProblemDiscoveryEngine.discover() returns structured problem candidates
  □ DeploymentEngine.compute_deployment_readiness() returns readiness_score in [0,100]
  □ DiscussionModerationEngine.classify_contribution() auto-classifies correctly
  □ POST /api/v1/solutions/problems/submit returns impact_score + priority_score
  □ POST /api/v1/solutions/discussions/{id}/convert returns synthesis + impact + feasibility
  □ POST /api/v1/solutions/grants/generate returns application_text + export_ready=True
  □ All 6 Idea Hub AIRequests carry ip_protected=True (PROBLEM_ANALYSIS,
      SOLUTION_SYNTHESIS, FEASIBILITY_ESTIMATE, DEPLOYMENT_PLANNING, GRANT_MATCHING)

DOCUMENT GENERATION ENGINE
  □ All 8 document types have section schemas (get_section_schema returns > 0 items)
  □ All 8 document types have page estimates for all 3 styles
  □ Investor mode prompt contains "INVESTOR MODE", "RISK SCORING", "RECOMMENDATION"
  □ ExportService.generate_shareable_link() returns URL with expiry parameter
  □ ExportService.export_to_pdf() returns ready=True
  □ ExportService.export_pitch_deck() returns ready=True with .pptx URL
  □ DocumentGenerationService.get_available_templates() returns 8 types
  □ All document AIRequests carry ip_protected=True
  □ POST /api/v1/documents/generate returns content + shareable_link + export URLs
  □ POST /api/v1/documents/investor-pack batches 4 documents in one call

CELERY
  □ All 14 scheduled tasks registered in Celery Beat
  □ Task wcrs_gsis_refresh runs every 30 minutes
  □ Task daily_tour_guide scheduled for 06:00 daily
  □ Task problem_discovery_daily scheduled for 06:00 daily
  □ Task discussion_moderation_hourly runs every hour
  □ Task impact_snapshot_daily scheduled for 01:00 daily
  □ Task document_cleanup_weekly scheduled for Sunday 03:00
  □ Monthly credit reset scheduled for 1st of month 00:00

SECURITY
  □ DEBUG=False in production
  □ SECRET_KEY is cryptographically random (256-bit) -- not the example value
  □ CORS restricted to your actual domain(s) -- not allow_origins=["*"]
  □ .env is in .gitignore and NOT committed to git
  □ API keys stored in AWS Secrets Manager (production) -- not .env files
  □ Rate limiting active in Redis
  □ RLS policies applied via apply_rls_policies(engine) -- verify with:
      SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
  □ techit_app role cannot BYPASSRLS (verify: \du in psql)
  □ techit_system role BYPASSRLS limited to IP detection queries only

MONITORING
  □ Sentry connected and receiving test events
  □ Alert configured: user AI cost > $10/month
  □ Alert configured: single request cost > $0.50
  □ Alert configured: agent failure rate > 10%
  □ Alert configured: > 20% projects stagnating (decay_factor < 0.70)
  □ Alert configured: idea_embeddings table not growing (embedding creation broken)
  □ Celery Flower secured with basic auth (production)
```

---

## Celery Scheduled Tasks

| Job | Schedule | Description |
|-----|----------|-------------|
| `daily_tour_guide` | `0 6 * * *` | Daily check-in for all active users |
| `weekly_summaries` | `0 18 * * 0` | Weekly Tour Guide summaries (Sun 18:00) |
| `daily_investor_signals` | `0 0 * * *` | EVI-I + investor signal refresh |
| `adaptive_curriculum_weekly` | `0 2 * * 1` | Curriculum for new users (Mon 02:00) |
| `wcrs_gsis_refresh` | `*/30 * * * *` | GSIS + WCRS refresh for all projects |
| `stagnation_roster` | `0 7 * * *` | Flag stagnating projects + re-engagement |
| `monthly_credit_reset` | `0 0 1 * *` | Reset subscription credit allocations |
| `admin_anomaly_scan` | `*/15 * * * *` | Continuous abuse/anomaly monitoring |
| `investor_alert_check` | `*/5 * * * *` | Watchlist threshold alerts |
| `problem_discovery_daily` | `0 6 * * *` | Auto-discover problems from external signals |
| `discussion_moderation_hourly` | `0 * * * *` | Moderate active discussion threads |
| `deployment_status_refresh` | `*/15 * * * *` | Refresh deployment status + beneficiary counts |
| `document_cleanup_weekly` | `0 3 * * 0` | Archive expired document share links |
| `impact_snapshot_daily` | `0 1 * * *` | Snapshot impact scores for active deployments |

---

## Cost at Scale

| Scale | Infrastructure | AI Costs | Total/Month | MRR |
|-------|----------------|----------|-------------|-----|
| 1K users | $200 | $2,100 | $2,300 | $59,000 |
| 10K users | $800 | $20,100 | $20,900 | $593,450 |
| 100K users | $4,200 | $190,000 | $194,200 | $5.9M |

**Gross margin: ~96.5%**

---

## Security

| Layer | Implementation |
|-------|----------------|
| Auth | JWT (python-jose) |
| Authorization | Role + subscription tier gates on every request |
| AI safety | SafetyEngine -- credits, permissions, injection, IP fingerprinting |
| Data isolation | PostgreSQL RLS -- 9 tables, project-scoped, techit_app non-superuser |
| Prompt injection | Pattern-matching on 13 known injection templates |
| Rate limiting | Redis-backed per-user-per-hour counters |
| Secrets | AWS Secrets Manager in production (never in .env files) |
| IP protection | Three layers: SHA-256 fingerprint + pgvector similarity + RLS |

### IP Protection Architecture (Three Layers)

**Layer 1 -- SHA-256 Fingerprinting**
Every `ip_protected=True` AIRequest is stamped with a SHA-256 hash of its payload by `SafetyEngine._fingerprint()` before the AI call. The fingerprint is stored in `ai_outputs.input_data["_ip_fingerprint"]` for audit, in `idea_embeddings.idea_fingerprint` for exact-match deduplication, and returned to callers for storage in project records. `VentureIntakeAgent` fingerprints every startup idea on intake. `IdeaSolutionHubService.submit_problem()` fingerprints every problem submission.

**Layer 2 -- Vector Similarity Leak Detection (pgvector)**
Every idea and solution is embedded using `text-embedding-3-small` (1536 dimensions) and stored in `idea_embeddings`. The `idea_similarity_check` reference query runs cosine similarity across all stored embeddings. Similarity ≥ 0.95 triggers an IP alert and blocks the result. This runs as the `techit_system` role (`BYPASSRLS`) -- the query returns only `project_id` and `similarity` score, never `idea_text`. `SafetyEngine.check_similarity_leak()` handles exact-match checking at application level.

**Layer 3 -- Row-Level Security (PostgreSQL RLS)**
Applied via `database_schema.apply_rls_policies(engine)` after migration. Covers 9 tables: `projects`, `ai_outputs`, `idea_embeddings`, `generated_documents`, `document_exports`, `solution_projects`, `grant_applications`, `credit_ledger`, `paywall_hits`. The application connects as `techit_app` (non-superuser) so RLS always applies. An investor visibility exception exposes score and stage metadata only -- never raw idea text. The `techit_system` role with `BYPASSRLS` is used exclusively for IP leak detection queries.

**Operations protected by `ip_protected=True`**

| Module | Operation | Task Type |
|--------|-----------|-----------|
| Incubation Hub | VentureIntakeAgent | IDEA_EVALUATION |
| Incubation Hub | UnicornEvaluatorAgent | UNICORN_ANALYSIS |
| Incubation Hub | BusinessPlanGeneratorAgent | EXECUTIVE_SUMMARY, BUSINESS_PLAN |
| Incubation Hub | PivotIntelligenceAgent | PIVOT_INTELLIGENCE |
| Incubation Hub | RiskEvaluatorAgent | RISK_ANALYSIS |
| Investor | generate_investor_readiness_report | INVESTOR_READINESS |
| Idea & Solution Hub | submit_problem, analyze_problem | PROBLEM_ANALYSIS |
| Idea & Solution Hub | convert_to_solution | SOLUTION_SYNTHESIS |
| Idea & Solution Hub | run_feasibility_estimate | FEASIBILITY_ESTIMATE |
| Idea & Solution Hub | create_deployment | DEPLOYMENT_PLANNING |
| Idea & Solution Hub | generate_grant_application | GRANT_MATCHING |
| Document Generation | generate_document (all 8 types) | DOCUMENT_* |

---

## Core Principles

1. **GSIS is the master score** -- every section feeds into it; investors and founders see the same truth
2. **EVI-I is distinct from EVI** -- founder momentum ≠ investor execution signal
3. **Training duration is computed, not scheduled** -- time-to-MVP engine, not "Week 1"
4. **Billing is hybrid** -- subscription + PAYG run simultaneously; subscription depletes first
5. **Paywalls trigger at momentum moments** -- taste value, then block progress
6. **Decay is anti-gaming** -- `e^(−0.02×d)` makes inactivity immediately punishing in rankings
7. **Prompts are data** -- stored in `ai_prompts` table, versioned, A/B-testable
8. **No vendor lock-in** -- ModelRouter abstracts all providers with fallback chains
9. **Everything logs** -- every AI execution recorded with cost, credits, model, and tokens
10. **IP protection is non-negotiable** -- ideas fingerprinted, isolated, similarity-monitored
11. **Problems are first-class citizens** -- not every solution is a startup; NGOs, policy, and infrastructure are equal pathways
12. **Documents are execution outputs** -- AI generates investor-ready documents from analysis already computed, eliminating weeks of manual work
13. **Speed is a feature, not a goal** -- from prompt to live scaffold in under 60 seconds; from scaffold to investor-ready company in under 30 days

---

## What TechIT Becomes

With this architecture deployed, TechIT becomes:

- **For Founders**: An AI co-founder that evaluates your idea against the Unicorn model, builds your strategy, designs your tech stack, generates your product scaffold, deploys your first live version, tracks your execution with GSIS and EVI-I, and adapts your training to your actual time-to-MVP -- all without leaving the platform. Not a plan. A running product.

- **For Investors**: A real-time deal flow intelligence engine with EVI-I execution signals on every startup -- 6-dimensional, decay-adjusted, narrative-explained. Not just deal flow. Signal.

- **For Builders**: A talent marketplace with AI-matched projects, adaptive role-specific training, and credibility scoring that compounds with every contribution.

- **For Accelerators**: A cohort management system where AI evaluates every team continuously against GSIS, flags stagnation with decay scores, and adapts training to each founder's pace.

- **For NGOs and Governments**: A structured problem-solving infrastructure -- submit real-world problems, get AI-synthesised solutions, plan real-world deployments, generate grant applications, and measure field impact. Not a startup tool. A global execution platform.

- **For Communities and Researchers**: A problem intelligence layer that discovers underserved crises before anyone submits them, matches existing solutions globally, and closes the feedback loop from deployment back to optimisation.

> *TechIT is not a platform for startups. TechIT is the operating system through which innovation happens globally.*

---

*Last Updated: April 2026 | TechIT AI Orchestration Layer v3.0*
*Files: 11 | Lines: ~19,000+ | Agents: 34 | Scoring Models: 20 | DB Tables: 42 | TaskTypes: 51 | Celery Jobs: 14*
*IP Protection: SHA-256 Fingerprinting + pgvector Similarity + PostgreSQL RLS (9 tables)*
