"""
TECHIT -- IDEA & SOLUTION HUB
==============================
Module: idea_solution_hub.py
Layer:  Incubation Hub Extension -- Problem-Driven Pathway

Design Philosophy
─────────────────
Most platforms start with: "I have a startup idea."
TechIT also serves:        "Here is a real-world problem that needs solving."

This module introduces a second entry pathway into the Incubation Hub --
the Problem-Driven Pathway -- where users, communities, NGOs, researchers,
and governments post real-world problems and the platform structures,
discusses, synthesises, and converts them into funded, deployed solutions.

Route: /incubator/solutions

Platform Sections Served
────────────────────────
  /incubator/solutions                -> Main dashboard
  /incubator/solutions/problems       -> Global Problems Board
  /incubator/solutions/discussions    -> Idea Discussion Threads
  /incubator/solutions/builder        -> Solution Builder
  /incubator/solutions/deployments    -> Active Deployments
  /incubator/solutions/impact         -> Global Impact Dashboard
  /incubator/solutions/funding        -> Funding & Grants Layer
  /incubator/solutions/marketplace    -> Impact Marketplace

Two Entry Pathways
──────────────────
  A. IDEA-DRIVEN  (existing)  -- "I want to build X" -> Startup Builder
  B. PROBLEM-DRIVEN  (new)    -- "Here is a problem" -> Idea & Solution Hub

Solution Types Supported
─────────────────────────
  - For-profit startup
  - Social initiative (NGO)
  - Public policy proposal
  - Community project
  - Research project
  - Infrastructure program
  - Service-based solution (not every solution is an app)

AI Roles in This Hub
─────────────────────
  1. Problem Analyzer     -- expands scope, adds missing context
  2. Solution Synthesizer -- combines best discussion ideas
  3. Feasibility Engine   -- cost, complexity, timeline estimates
  4. Impact Predictor     -- real-world effect estimate
  5. Discovery Engine     -- finds problems before users do
  6. Solution Matcher     -- reuses existing solutions globally

New TaskTypes added to ai_router_core.py
─────────────────────────────────────────
  PROBLEM_ANALYSIS       SOLUTION_SYNTHESIS     IMPACT_PREDICTION
  FEASIBILITY_ESTIMATE   PROBLEM_DISCOVERY      SOLUTION_MATCHING
  DEPLOYMENT_PLANNING    GRANT_MATCHING         DISCUSSION_MODERATION
  FIELD_FEEDBACK_ANALYSIS

New AgentTypes added to agent_orchestration.py
────────────────────────────────────────────────
  PROBLEM_ANALYZER       SOLUTION_SYNTHESIZER   IMPACT_PREDICTOR
  FEASIBILITY_ESTIMATOR  PROBLEM_DISCOVERY      SOLUTION_MATCHER
  DEPLOYMENT_PLANNER     GRANT_MATCHER
  DISCUSSION_MODERATOR   FIELD_FEEDBACK_AGENT

New DB Tables (added to database_schema.py)
────────────────────────────────────────────
  problem_nodes            solution_projects       discussion_threads
  discussion_contributions solution_deployments    field_feedback
  impact_snapshots         grant_applications
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ============================================================================
# ENUMERATIONS
# ============================================================================

class ProblemCategory(Enum):
    HEALTH              = "health"
    AGRICULTURE         = "agriculture"
    EDUCATION           = "education"
    CLIMATE             = "climate"
    INFRASTRUCTURE      = "infrastructure"
    FINANCE             = "finance"
    GOVERNANCE          = "governance"
    WATER_SANITATION    = "water_sanitation"
    ENERGY              = "energy"
    FOOD_SECURITY       = "food_security"
    GENDER_EQUALITY     = "gender_equality"
    ECONOMIC_INCLUSION  = "economic_inclusion"
    TECHNOLOGY_ACCESS   = "technology_access"
    HOUSING             = "housing"
    JUSTICE             = "justice"
    ENVIRONMENT         = "environment"
    OTHER               = "other"


class ProblemUrgency(Enum):
    CRITICAL    = "critical"    # 🔴 Immediate action needed
    HIGH        = "high"        # 🟠 High priority
    EMERGING    = "emerging"    # 🟡 Emerging opportunity
    LONG_TERM   = "long_term"   # 🔵 Long-term research


class ProblemSource(Enum):
    USER_SUBMITTED      = "user_submitted"
    AI_DISCOVERED       = "ai_discovered"     # automated discovery engine
    NGO_REPORTED        = "ngo_reported"
    GOVERNMENT_DATASET  = "government_dataset"
    RESEARCH_PAPER      = "research_paper"
    NEWS_SIGNAL         = "news_signal"
    SOCIAL_SIGNAL       = "social_signal"
    PARTNER_SUBMITTED   = "partner_submitted"


class SolutionType(Enum):
    STARTUP_FOR_PROFIT  = "startup_for_profit"
    SOCIAL_INITIATIVE   = "social_initiative"     # NGO
    PUBLIC_POLICY       = "public_policy"
    COMMUNITY_PROJECT   = "community_project"
    RESEARCH_PROJECT    = "research_project"
    INFRASTRUCTURE      = "infrastructure"
    SERVICE_BASED       = "service_based"
    HYBRID              = "hybrid"


class FundingType(Enum):
    REVENUE             = "revenue"               # commercial
    GRANTS              = "grants"
    DONATIONS           = "donations"
    IMPACT_INVESTORS    = "impact_investors"
    CSR_PARTNERSHIPS    = "csr_partnerships"
    GOVERNMENT_FUNDING  = "government_funding"
    DEVELOPMENT_BANKS   = "development_banks"
    HYBRID              = "hybrid"


class DeploymentMode(Enum):
    PILOT_PROGRAM       = "pilot_program"
    NGO_ROLLOUT         = "ngo_rollout"
    GOVERNMENT_PARTNER  = "government_partner"
    STARTUP_LAUNCH      = "startup_launch"
    CSR_EXECUTION       = "csr_execution"
    COMMUNITY_LED       = "community_led"


class DeploymentStatus(Enum):
    PENDING             = "pending"
    ACTIVE              = "active"
    SCALING             = "scaling"
    COMPLETED           = "completed"
    PAUSED              = "paused"


class ContributionType(Enum):
    IDEA                = "idea"
    INSIGHT             = "insight"
    RESOURCE            = "resource"
    CRITIQUE            = "critique"
    DATA_EVIDENCE       = "data_evidence"


class SolutionStage(Enum):
    DISCUSSION          = "discussion"
    VALIDATED           = "validated"
    BUILDING            = "building"
    PILOTING            = "piloting"
    DEPLOYED            = "deployed"
    SCALED              = "scaled"


class ContributorRole(Enum):
    ENGINEER            = "engineer"
    DESIGNER            = "designer"
    FIELD_OPERATOR      = "field_operator"
    NGO_PARTNER         = "ngo_partner"
    POLICY_EXPERT       = "policy_expert"
    FUNDRAISER          = "fundraiser"
    CO_FOUNDER          = "co_founder"
    VOLUNTEER           = "volunteer"
    PARTNER_ORG         = "partner_organisation"
    RESEARCHER          = "researcher"
    DOMAIN_EXPERT       = "domain_expert"


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class ProblemNode:
    """
    A structured real-world problem posted to the Global Problems Board.

    Users submit either a startup idea (Idea-Driven pathway) or a problem
    statement (Problem-Driven pathway). ProblemNodes are the entry point
    for the Problem-Driven pathway.

    Route: POST /api/v1/solutions/problems/submit
    """
    problem_id:         str = field(default_factory=lambda: str(uuid.uuid4()))
    title:              str = ""
    description:        str = ""
    location:           str = "Global"           # Global or specific region/country
    category:           ProblemCategory = ProblemCategory.OTHER
    who_is_affected:    str = ""                 # Who suffers from this problem
    current_solutions:  List[str] = field(default_factory=list)  # existing but failed
    urgency:            ProblemUrgency = ProblemUrgency.EMERGING
    source:             ProblemSource = ProblemSource.USER_SUBMITTED
    submitted_by:       Optional[str] = None     # user_id
    impact_score:       float = 0.0              # ImpactScore 0–100
    priority_score:     float = 0.0              # ProblemPriorityScore 0–100
    engagement_count:   int = 0                  # contributions + discussions
    ai_summary:         Optional[str] = None     # AI-generated problem summary
    stakeholder_map:    Optional[Dict] = None    # AI-generated stakeholder analysis
    related_problems:   List[str] = field(default_factory=list)   # problem_ids
    sdg_alignment:      List[str] = field(default_factory=list)   # UN SDG goals
    tags:               List[str] = field(default_factory=list)
    is_ai_discovered:   bool = False
    verified:           bool = False
    created_at:         datetime = field(default_factory=datetime.utcnow)
    updated_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class DiscussionContribution:
    """
    A structured contribution to a problem discussion thread.

    Unlike Reddit-style chaos, each contribution has a type that
    classifies its nature: Idea, Insight, Resource, Critique, or Data Evidence.
    The AI layer summarises discussions, clusters ideas, and detects the
    strongest direction.
    """
    contribution_id:    str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_id:          str = ""
    problem_id:         str = ""
    author_id:          str = ""
    contribution_type:  ContributionType = ContributionType.IDEA
    content:            str = ""
    ai_quality_score:   float = 0.0      # 0–100, AI-assessed contribution quality
    upvotes:            int = 0
    is_ai_summarised:   bool = False
    cluster_label:      Optional[str] = None  # AI-assigned idea cluster
    created_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class SolutionProject:
    """
    A solution built from a problem discussion or directly proposed.

    Created when a discussion matures and a user clicks
    "Convert to Solution Project". Supports all solution types --
    not just startups, but also NGOs, policy proposals, community
    projects, and infrastructure programs.
    """
    solution_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    problem_id:         str = ""
    title:              str = ""
    description:        str = ""
    solution_type:      SolutionType = SolutionType.STARTUP_FOR_PROFIT
    funding_type:       FundingType = FundingType.REVENUE
    stage:              SolutionStage = SolutionStage.DISCUSSION
    impact_model:       str = ""         # how the solution creates impact
    execution_plan:     str = ""
    required_roles:     List[ContributorRole] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    estimated_cost_usd: Optional[float] = None
    estimated_timeline_weeks: Optional[int] = None

    # Scores
    impact_score:       float = 0.0      # ImpactScore 0–100
    feasibility_score:  float = 0.0      # 0–100
    sustainability_score: float = 0.0    # 0–100
    readiness_score:    float = 0.0      # MarketReady adaptation for non-profits

    # People and deployments
    contributors:       List[Dict] = field(default_factory=list)
    deployments:        List[str] = field(default_factory=list)  # deployment_ids
    created_by:         Optional[str] = None
    created_at:         datetime = field(default_factory=datetime.utcnow)
    updated_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class SolutionDeployment:
    """
    A real-world deployment of a validated solution.

    This is TechIT's critical differentiator -- solutions don't just sit
    in the platform. They get deployed to the real world with tracking,
    partner onboarding, resource allocation, and timeline management.
    """
    deployment_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    solution_id:        str = ""
    mode:               DeploymentMode = DeploymentMode.PILOT_PROGRAM
    status:             DeploymentStatus = DeploymentStatus.PENDING
    region:             str = ""
    partner_orgs:       List[str] = field(default_factory=list)
    resources_allocated: Dict[str, Any] = field(default_factory=dict)
    start_date:         Optional[datetime] = None
    target_end_date:    Optional[datetime] = None
    beneficiaries_target: int = 0
    beneficiaries_reached: int = 0
    deployment_checklist: List[Dict] = field(default_factory=list)
    notes:              str = ""
    created_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class FieldFeedback:
    """
    Real-world feedback collected after a solution is deployed.

    TechIT closes the loop: Problem -> Solution -> Deployment -> Feedback -> Optimisation.
    Most systems stop at launch. This one does not.
    """
    feedback_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id:      str = ""
    solution_id:        str = ""
    submitted_by:       Optional[str] = None
    usage_data:         Dict[str, Any] = field(default_factory=dict)
    impact_metrics:     Dict[str, Any] = field(default_factory=dict)
    field_report:       str = ""
    beneficiary_feedback: str = ""
    failure_points:     List[str] = field(default_factory=list)
    what_worked:        List[str] = field(default_factory=list)
    ai_analysis:        Optional[str] = None
    created_at:         datetime = field(default_factory=datetime.utcnow)


@dataclass
class GrantApplication:
    """
    A grant or funding application generated by the platform for a solution.
    """
    application_id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    solution_id:        str = ""
    funder_name:        str = ""
    funding_type:       FundingType = FundingType.GRANTS
    amount_requested_usd: float = 0.0
    application_text:   str = ""         # AI-generated application
    status:             str = "draft"    # draft / submitted / approved / rejected
    submitted_at:       Optional[datetime] = None
    created_at:         datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# IMPACT SCORING ENGINE
# ============================================================================

class ImpactScoringEngine:
    """
    Computes the TechIT Impact Score (0–100) for problems and solutions.

    Impact Score = (
        0.30 × people_affected_score  +
        0.25 × severity_score         +
        0.20 × scalability_score      +
        0.15 × sustainability_score   +
        0.10 × measurability_score
    ) × 100

    Also computes Problem Priority Score for the Global Problems Board:

    Priority Score = (
        0.25 × impact_score           +
        0.25 × urgency_score          +
        0.20 × funding_availability   +
        0.15 × political_feasibility  +
        0.15 × time_sensitivity
    ) × 100
    """

    @classmethod
    def compute_impact_score(
        cls,
        people_affected_millions:   float,   # estimated people affected
        severity:                   float,   # 0–10: how severe is the problem
        scalability:                float,   # 0–10: can solution scale globally
        sustainability:             float,   # 0–10: long-term viability
        measurability:              float,   # 0–10: can outcomes be measured
    ) -> Dict[str, Any]:
        """
        Impact Score = 0.30*PA + 0.25*SEV + 0.20*SCALE + 0.15*SUS + 0.10*MEAS

        people_affected_score: log-normalised to 0–10
          < 10K people   -> 1–3
          10K–1M         -> 4–6
          1M–100M        -> 7–8
          > 100M         -> 9–10
        """
        import math

        # Normalise people affected (log scale)
        if people_affected_millions <= 0:
            pa_score = 0.0
        elif people_affected_millions < 0.01:
            pa_score = 2.0
        elif people_affected_millions < 1.0:
            pa_score = 5.0
        elif people_affected_millions < 100.0:
            pa_score = 7.5
        else:
            pa_score = min(10.0, 7.5 + math.log10(people_affected_millions / 100) * 2)

        sev   = min(10.0, max(0.0, float(severity)))
        scale = min(10.0, max(0.0, float(scalability)))
        sus   = min(10.0, max(0.0, float(sustainability)))
        meas  = min(10.0, max(0.0, float(measurability)))

        raw = (
            0.30 * pa_score +
            0.25 * sev      +
            0.20 * scale    +
            0.15 * sus      +
            0.10 * meas
        ) * 10   # scale each component (max 10) -> total max 100

        score = round(min(100.0, max(0.0, raw)), 2)

        return {
            "impact_score":          score,
            "classification":        cls._classify_impact(score),
            "components": {
                "people_affected":   round(pa_score, 2),
                "severity":          sev,
                "scalability":       scale,
                "sustainability":    sus,
                "measurability":     meas,
            },
            "people_affected_millions": people_affected_millions,
        }

    @classmethod
    def _classify_impact(cls, score: float) -> str:
        if score >= 80: return "Transformative -- global scale potential"
        if score >= 65: return "High Impact -- significant population benefit"
        if score >= 50: return "Moderate Impact -- meaningful but localised"
        if score >= 35: return "Early Stage -- impact model needs strengthening"
        return "Limited -- refine problem scope and impact model"

    @classmethod
    def compute_priority_score(
        cls,
        impact_score:           float,   # from compute_impact_score
        urgency:                ProblemUrgency,
        funding_availability:   float,   # 0–10
        political_feasibility:  float,   # 0–10
        time_sensitivity:       float,   # 0–10
    ) -> Dict[str, Any]:
        """
        Priority Score = 0.25*IS + 0.25*URG + 0.20*FUND + 0.15*POL + 0.15*TIME

        Outputs the ranking colour:
          🔴 Critical (85+)
          🟠 High Priority (65–84)
          🟡 Emerging Opportunity (45–64)
          🔵 Long-term Research (0–44)
        """
        urgency_map = {
            ProblemUrgency.CRITICAL:  10.0,
            ProblemUrgency.HIGH:       7.5,
            ProblemUrgency.EMERGING:   5.0,
            ProblemUrgency.LONG_TERM:  2.5,
        }
        urg    = urgency_map.get(urgency, 5.0)
        fund   = min(10.0, max(0.0, float(funding_availability)))
        pol    = min(10.0, max(0.0, float(political_feasibility)))
        time   = min(10.0, max(0.0, float(time_sensitivity)))
        is_n   = impact_score / 10.0   # scale impact_score back to 0–10

        raw = (
            0.25 * is_n  +
            0.25 * urg   +
            0.20 * fund  +
            0.15 * pol   +
            0.15 * time
        ) * 10

        score = round(min(100.0, max(0.0, raw)), 2)
        colour, label = cls._classify_priority(score)

        return {
            "priority_score":  score,
            "colour":          colour,
            "label":           label,
            "components": {
                "impact":              round(is_n * 10, 2),
                "urgency":             urg * 10,
                "funding_availability": fund * 10,
                "political_feasibility": pol * 10,
                "time_sensitivity":    time * 10,
            },
        }

    @classmethod
    def _classify_priority(cls, score: float):
        if score >= 85: return ("🔴", "Critical -- Immediate Action")
        if score >= 65: return ("🟠", "High Priority")
        if score >= 45: return ("🟡", "Emerging Opportunity")
        return ("🔵", "Long-term Research")


# ============================================================================
# PROBLEM DISCOVERY ENGINE
# ============================================================================

class ProblemDiscoveryEngine:
    """
    Automatically discovers real-world problems before users submit them.

    Data sources:
      - News feeds (global + local)
      - Research paper abstracts
      - NGO situation reports
      - Government open datasets
      - Social media signal aggregators
      - Climate / agriculture / health surveillance data

    AI detects:
      - Emerging crises
      - Underserved sectors
      - Repeated systemic failures
      - Geographic problem clusters

    Output:
      - "High Priority Problem Alerts"
      - "Underserved Market Opportunities"
      - "Crisis Response Opportunities"

    In production: replace _fetch_signals() with real data pipeline
    integrations (RSS feeds, GDELT, ReliefWeb API, World Bank API, etc.)
    """

    SIGNAL_SOURCES = {
        "news":           "https://newsapi.org/v2/everything",
        "reliefweb":      "https://api.reliefweb.int/v1/reports",
        "world_bank":     "https://api.worldbank.org/v2/",
        "fao":            "https://www.fao.org/faostat/",
        "who":            "https://who.int/data/",
    }

    def discover(
        self,
        region:     Optional[str] = None,
        categories: Optional[List[ProblemCategory]] = None,
        limit:      int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Scan external signals and return candidate ProblemNodes.

        Production: call real APIs and run AI classification.
        Returns a list of structured problem candidates for human review.
        """
        signals = self._fetch_signals(region, categories)
        discoveries = []
        for signal in signals[:limit]:
            node = self._classify_signal(signal)
            if node:
                discoveries.append(node)
        return discoveries

    def _fetch_signals(
        self,
        region: Optional[str],
        categories: Optional[List[ProblemCategory]],
    ) -> List[Dict]:
        """
        Production: replace with real API calls to signal sources.
        Returns raw signal data for AI classification.
        """
        return [
            {
                "source":    "news_signal",
                "headline":  "Post-harvest losses rising in Sub-Saharan Africa",
                "region":    "Sub-Saharan Africa",
                "category":  "agriculture",
                "severity":  7.5,
                "recurrence": "systematic",
                "raw_url":   "https://example.com/article",
            },
            {
                "source":    "who_dataset",
                "headline":  "Rural maternal mortality rates 3x urban average",
                "region":    "West Africa",
                "category":  "health",
                "severity":  9.0,
                "recurrence": "persistent",
                "raw_url":   "https://who.int/data/example",
            },
        ]

    def _classify_signal(self, signal: Dict) -> Optional[Dict]:
        """
        Map a raw signal to a structured ProblemNode candidate.
        Production: pass through AI classification for richer context.
        """
        category_map = {
            "agriculture": ProblemCategory.AGRICULTURE,
            "health":      ProblemCategory.HEALTH,
            "education":   ProblemCategory.EDUCATION,
            "climate":     ProblemCategory.CLIMATE,
        }
        cat = category_map.get(signal.get("category", ""), ProblemCategory.OTHER)
        sev = signal.get("severity", 5.0)
        urgency = ProblemUrgency.CRITICAL if sev >= 8 else (
                  ProblemUrgency.HIGH      if sev >= 6 else ProblemUrgency.EMERGING)

        return {
            "title":       signal.get("headline", ""),
            "location":    signal.get("region", "Global"),
            "category":    cat.value,
            "urgency":     urgency.value,
            "source":      ProblemSource.AI_DISCOVERED.value,
            "severity":    sev,
            "raw_url":     signal.get("raw_url", ""),
            "is_ai_discovered": True,
        }


# ============================================================================
# SOLUTION MATCHING ENGINE
# ============================================================================

class SolutionMatchingEngine:
    """
    Matches existing solutions, startups, and NGOs to new problems.

    Instead of building from scratch every time, TechIT reuses intelligence
    globally -- a solution that worked in Kenya is matched to a similar
    problem in Nigeria.

    Match Sources:
      - Existing SolutionProjects in the platform
      - External startups (via Crunchbase / AngelList signals)
      - NGO databases (UN IATI, ReliefWeb)
      - Academic papers on similar interventions

    Match Score = (
        0.40 × category_similarity  +
        0.30 × region_similarity    +
        0.20 × solution_stage       +
        0.10 × funding_compatibility
    ) × 100
    """

    def find_matches(
        self,
        problem: ProblemNode,
        existing_solutions: List[SolutionProject],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find existing solutions, startups, or NGOs that map to a new problem.
        Returns ranked list with match scores and explanations.
        """
        matches = []
        for sol in existing_solutions:
            score = self._score_match(problem, sol)
            if score["match_score"] >= 40.0:
                matches.append({
                    "solution_id":    sol.solution_id,
                    "solution_title": sol.title,
                    "solution_type":  sol.solution_type.value,
                    "stage":          sol.stage.value,
                    "match_score":    score["match_score"],
                    "match_reason":   score["reason"],
                    "can_reuse":      sol.stage.value in ("deployed", "scaled"),
                    "contact_available": True,
                })

        matches.sort(key=lambda x: x["match_score"], reverse=True)
        return matches[:limit]

    def _score_match(
        self, problem: ProblemNode, solution: SolutionProject
    ) -> Dict[str, Any]:
        """
        Compute match score between a problem and an existing solution.
        Production: use vector similarity on problem + solution embeddings.
        """
        # Simplified category matching -- production uses semantic similarity
        problem_cat   = problem.category.value
        solution_tags = getattr(solution, "tags", [])
        category_sim  = 8.0 if problem_cat in solution_tags else 5.0

        # Stage bonus (deployed solutions are immediately reusable)
        stage_bonus = {
            "deployed": 9.0, "scaled": 10.0, "piloting": 7.0,
            "building": 5.0, "validated": 4.0, "discussion": 2.0,
        }.get(solution.stage.value, 3.0)

        # Region match
        region_sim = 7.0 if solution.solution_type != SolutionType.PUBLIC_POLICY else 5.0

        # Funding compatibility
        fund_compat = 8.0 if solution.funding_type != FundingType.REVENUE else 6.0

        raw = (
            0.40 * category_sim +
            0.30 * region_sim   +
            0.20 * stage_bonus  +
            0.10 * fund_compat
        ) * 10

        score  = round(min(100.0, max(0.0, raw)), 2)
        reason = (
            f"Category overlap with {problem_cat}. "
            f"Solution is at '{solution.stage.value}' stage -- "
            f"{'immediately reusable' if score >= 70 else 'adaptable'}."
        )
        return {"match_score": score, "reason": reason}


# ============================================================================
# DEPLOYMENT ENGINE
# ============================================================================

class DeploymentEngine:
    """
    Manages real-world deployment of validated solutions.

    TechIT does not just build solutions -- it deploys them.
    This is the core differentiator from every other innovation platform.

    Deployment Modes:
      Pilot Program       -- small region test
      NGO Rollout         -- NGO-led field execution
      Government Partner  -- government agency partnership
      Startup Launch      -- commercial product launch
      CSR Execution       -- corporate social responsibility program
      Community Led       -- grassroots community implementation

    Each deployment has:
      - Deployment checklist
      - Region selection
      - Partner onboarding
      - Resource allocation
      - Timeline tracking
      - Field feedback loop
    """

    DEFAULT_CHECKLISTS: Dict[DeploymentMode, List[str]] = {
        DeploymentMode.PILOT_PROGRAM: [
            "Define pilot region and scope",
            "Identify beneficiary population",
            "Secure pilot funding",
            "Recruit field team",
            "Set up data collection system",
            "Define success metrics",
            "Establish feedback channels",
            "Run 30-day pilot",
            "Collect and analyse results",
            "Decision: scale / pivot / stop",
        ],
        DeploymentMode.NGO_ROLLOUT: [
            "Identify NGO partner(s)",
            "Sign MOU / partnership agreement",
            "Transfer solution assets",
            "Train NGO field staff",
            "Establish reporting cadence",
            "Allocate resources and budget",
            "Launch rollout in target region",
            "Monitor field reports",
            "Measure impact outcomes",
        ],
        DeploymentMode.GOVERNMENT_PARTNER: [
            "Identify government department",
            "Submit policy proposal",
            "Regulatory compliance review",
            "Government sign-off",
            "Pilot under government oversight",
            "Integration with government systems",
            "Public launch",
            "Annual impact reporting",
        ],
        DeploymentMode.STARTUP_LAUNCH: [
            "MVP ready",
            "Market validation complete",
            "Legal entity established",
            "Funding secured",
            "Go-to-market strategy finalised",
            "Beta users onboarded",
            "Public launch",
            "Revenue tracking active",
        ],
    }

    def create_deployment_plan(
        self,
        solution: SolutionProject,
        mode: DeploymentMode,
        region: str,
        beneficiaries_target: int,
    ) -> SolutionDeployment:
        """Create a structured deployment plan for a validated solution."""
        checklist_items = [
            {"item": item, "completed": False}
            for item in self.DEFAULT_CHECKLISTS.get(mode, [])
        ]
        return SolutionDeployment(
            solution_id=solution.solution_id,
            mode=mode,
            status=DeploymentStatus.PENDING,
            region=region,
            beneficiaries_target=beneficiaries_target,
            deployment_checklist=checklist_items,
        )

    def advance_deployment(
        self,
        deployment: SolutionDeployment,
        completed_item: str,
        notes: str = "",
    ) -> SolutionDeployment:
        """Mark a checklist item complete and update deployment status."""
        for item in deployment.deployment_checklist:
            if item["item"] == completed_item:
                item["completed"] = True
                break

        completed = sum(1 for i in deployment.deployment_checklist if i["completed"])
        total     = len(deployment.deployment_checklist)
        pct       = completed / max(total, 1)

        if pct >= 1.0:
            deployment.status = DeploymentStatus.COMPLETED
        elif pct >= 0.5:
            deployment.status = DeploymentStatus.ACTIVE
        elif pct > 0:
            deployment.status = DeploymentStatus.ACTIVE

        if notes:
            deployment.notes = f"{deployment.notes}\n[{datetime.utcnow().isoformat()}] {notes}".strip()

        return deployment

    def compute_deployment_readiness(
        self, solution: SolutionProject
    ) -> Dict[str, Any]:
        """
        Readiness assessment before allowing deployment initiation.
        Adapted version of Market Readiness for non-commercial solutions.
        """
        criteria = {
            "problem_validated":    len(solution.description) > 100,
            "solution_documented":  len(solution.execution_plan) > 50,
            "impact_model_defined": solution.impact_score > 0,
            "funding_identified":   solution.funding_type != FundingType.REVENUE or True,
            "team_roles_defined":   len(solution.required_roles) > 0,
            "feasibility_checked":  solution.feasibility_score > 0,
        }
        score = round(sum(criteria.values()) / len(criteria) * 100, 1)
        ready = score >= 80.0

        return {
            "readiness_score":    score,
            "ready_to_deploy":    ready,
            "criteria":           criteria,
            "missing":            [k for k, v in criteria.items() if not v],
            "recommendation":     "Ready for deployment" if ready else
                                  f"Address {len([v for v in criteria.values() if not v])} remaining criteria",
        }


# ============================================================================
# DISCUSSION MODERATION ENGINE
# ============================================================================

class DiscussionModerationEngine:
    """
    AI-powered discussion moderator for problem threads.

    Unlike Reddit-style chaos:
      - Each contribution is typed (Idea / Insight / Resource / Critique / Data)
      - AI summarises the thread regularly
      - AI clusters ideas into thematic groups
      - AI detects the strongest direction
      - AI removes noise and highlights signal

    Methods map to TaskType.DISCUSSION_MODERATION in ai_router_core.py
    """

    def classify_contribution(
        self, content: str
    ) -> ContributionType:
        """
        Classify a contribution automatically based on content patterns.
        Production: use AI classifier.
        """
        content_lower = content.lower()
        if any(w in content_lower for w in ["data shows", "research says", "study found", "evidence"]):
            return ContributionType.DATA_EVIDENCE
        if any(w in content_lower for w in ["however", "but wait", "problem with", "weakness"]):
            return ContributionType.CRITIQUE
        if any(w in content_lower for w in ["here is a link", "resource", "tool", "platform exists"]):
            return ContributionType.RESOURCE
        if any(w in content_lower for w in ["insight", "pattern i noticed", "from experience"]):
            return ContributionType.INSIGHT
        return ContributionType.IDEA

    def cluster_contributions(
        self, contributions: List[DiscussionContribution]
    ) -> Dict[str, List[str]]:
        """
        Group contributions into thematic clusters.
        Production: use embedding similarity + k-means clustering.
        """
        clusters: Dict[str, List[str]] = {
            "Technology Solutions":    [],
            "Policy Interventions":    [],
            "Community Approaches":    [],
            "Market-Based Solutions":  [],
            "Infrastructure Needs":    [],
            "Other":                   [],
        }
        for c in contributions:
            if c.contribution_type == ContributionType.DATA_EVIDENCE:
                clusters["Other"].append(c.contribution_id)
            elif c.contribution_type == ContributionType.IDEA:
                # Production: AI classifies into correct cluster
                clusters["Technology Solutions"].append(c.contribution_id)
        return clusters

    def detect_strongest_direction(
        self, contributions: List[DiscussionContribution]
    ) -> Dict[str, Any]:
        """
        Identify the most promising solution direction from the discussion.
        Production: score clusters by upvotes + AI quality scores + evidence.
        """
        if not contributions:
            return {"direction": "No contributions yet", "confidence": 0.0}

        ideas     = [c for c in contributions if c.contribution_type == ContributionType.IDEA]
        evidence  = [c for c in contributions if c.contribution_type == ContributionType.DATA_EVIDENCE]
        avg_quality = sum(c.ai_quality_score for c in contributions) / len(contributions)

        direction = (
            "Technology-led solution with community implementation"
            if len(ideas) > len(evidence) else
            "Evidence-based intervention with policy backing"
        )
        confidence = min(100.0, round(avg_quality * len(contributions) / 10, 1))

        return {
            "direction":           direction,
            "confidence":          confidence,
            "total_contributions": len(contributions),
            "idea_count":          len(ideas),
            "evidence_count":      len(evidence),
            "ready_to_convert":    len(contributions) >= 5 and confidence >= 60,
        }


# ============================================================================
# IDEA & SOLUTION HUB SERVICE
# ============================================================================

class IdeaSolutionHubService:
    """
    Service layer for the Idea & Solution Hub.
    Integrates with TechITAIBrain for all AI operations.

    All AI calls use TaskTypes defined in ai_router_core.py:
      PROBLEM_ANALYSIS, SOLUTION_SYNTHESIS, IMPACT_PREDICTION,
      FEASIBILITY_ESTIMATE, PROBLEM_DISCOVERY, SOLUTION_MATCHING,
      DEPLOYMENT_PLANNING, GRANT_MATCHING, DISCUSSION_MODERATION,
      FIELD_FEEDBACK_ANALYSIS

    API Endpoints served
    ─────────────────────
    GLOBAL PROBLEMS BOARD
      POST /api/v1/solutions/problems/submit          2 credits  Free+
      GET  /api/v1/solutions/problems/board           0 credits  Free+
      GET  /api/v1/solutions/problems/{id}            0 credits  Free+
      POST /api/v1/solutions/problems/{id}/analyze    2 credits  Builder+
      GET  /api/v1/solutions/problems/discover        2 credits  Builder+
      GET  /api/v1/solutions/problems/match/{id}      2 credits  Builder+

    IDEA DISCUSSIONS
      POST /api/v1/solutions/discussions/{id}/contribute   1 credit  Free+
      GET  /api/v1/solutions/discussions/{id}/summary      1 credit  Free+
      GET  /api/v1/solutions/discussions/{id}/clusters     1 credit  Builder+
      POST /api/v1/solutions/discussions/{id}/convert      3 credits  Founder Pro+

    SOLUTION PROJECTS
      POST /api/v1/solutions/projects/create          3 credits  Founder Pro+
      GET  /api/v1/solutions/projects/{id}            0 credits  Free+
      POST /api/v1/solutions/projects/{id}/synthesize 3 credits  Founder Pro+
      POST /api/v1/solutions/projects/{id}/feasibility 2 credits  Builder+
      GET  /api/v1/solutions/projects/{id}/impact     1 credit   Free+

    DEPLOYMENT
      POST /api/v1/solutions/deployments/create       2 credits  Founder Pro+
      GET  /api/v1/solutions/deployments/{id}         0 credits  Free+
      POST /api/v1/solutions/deployments/{id}/advance 0 credits  Free+
      POST /api/v1/solutions/deployments/{id}/feedback 1 credit  Free+
      GET  /api/v1/solutions/deployments/{id}/readiness 0 credits Free+

    FUNDING
      POST /api/v1/solutions/grants/generate          3 credits  Founder Pro+
      GET  /api/v1/solutions/grants/{solution_id}     0 credits  Free+
      GET  /api/v1/solutions/funding/match/{id}       2 credits  Builder+

    IMPACT DASHBOARD
      GET  /api/v1/solutions/impact/global            0 credits  Free+
      GET  /api/v1/solutions/impact/{solution_id}     0 credits  Free+
    """

    def __init__(self, brain) -> None:
        self.brain         = brain
        self.impact_engine = ImpactScoringEngine()
        self.discovery     = ProblemDiscoveryEngine()
        self.matcher       = SolutionMatchingEngine()
        self.deployment    = DeploymentEngine()
        self.moderator     = DiscussionModerationEngine()

    # ── PROBLEM SUBMISSION ─────────────────────────────────────────────────

    async def submit_problem(
        self,
        user_context,
        title:            str,
        description:      str,
        category:         str,
        location:         str,
        who_is_affected:  str,
        current_solutions: List[str],
        urgency:          str,
        people_affected_millions: float = 1.0,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/solutions/problems/submit -- 2 credits, Free+

        Accepts a real-world problem statement and:
          1. Computes Impact Score
          2. Computes Priority Score
          3. Runs AI problem analysis (expands scope + stakeholder map)
          4. Checks for similar existing problems (deduplication)
          5. Creates ProblemNode
        """
        from ai_router_core import AIRequest, TaskType

        cat_enum = ProblemCategory(category) if category in [e.value for e in ProblemCategory] else ProblemCategory.OTHER
        urg_enum = ProblemUrgency(urgency) if urgency in [e.value for e in ProblemUrgency] else ProblemUrgency.EMERGING

        impact   = self.impact_engine.compute_impact_score(
            people_affected_millions, 7.0, 6.0, 6.0, 7.0
        )
        priority = self.impact_engine.compute_priority_score(
            impact["impact_score"], urg_enum, 6.0, 5.0, 7.0
        )

        ai_resp = await self.brain.process(AIRequest(
            task_type=TaskType.PROBLEM_ANALYSIS,
            user_context=user_context,
            input_data={
                "title":           title,
                "description":     description,
                "category":        category,
                "location":        location,
                "who_affected":    who_is_affected,
                "failed_solutions": current_solutions,
                "urgency":         urgency,
                "impact_score":    impact["impact_score"],
            },
            max_tokens=3000,
            ip_protected=True,  # Problem descriptions are proprietary IP
        ))

        node = ProblemNode(
            title=title, description=description,
            location=location, category=cat_enum,
            who_is_affected=who_is_affected,
            current_solutions=current_solutions,
            urgency=urg_enum,
            submitted_by=user_context.user_id,
            impact_score=impact["impact_score"],
            priority_score=priority["priority_score"],
            ai_summary=ai_resp.output,
        )

        # ── IP PROTECTION: fingerprint and embed the problem description ──────
        # SHA-256 fingerprint for exact-match deduplication.
        # Vector embedding for semantic similarity leak detection.
        # Stored in problem_nodes.idea_fingerprint (via problem-level embedding).
        # Any future problem with cosine similarity ≥ 0.95 triggers an IP alert.
        problem_text = f"{title} {description} {who_is_affected}".strip()
        import hashlib as _hl
        problem_fingerprint = _hl.sha256(problem_text.encode()).hexdigest()
        # Production: call embedding API then INSERT into a problem_embeddings
        # table (extend database_schema.py) or store in problem_nodes.fingerprint.
        # embed_resp = await self.brain.process(AIRequest(
        #     task_type=TaskType.EMBEDDINGS,
        #     user_context=user_context,
        #     input_data={"text": problem_text, "model": "text-embedding-3-small"},
        #     ip_protected=True,
        # ))
        # INSERT INTO problem_nodes SET fingerprint = problem_fingerprint
        # INSERT INTO idea_embeddings (embedding, idea_fingerprint, idea_text,
        #     is_protected, leak_detection_enabled, leak_detection_threshold)
        # ── END IP PROTECTION ─────────────────────────────────────────────────

        return {
            "problem_id":       node.problem_id,
            "title":            node.title,
            "impact_score":     impact,
            "priority_score":   priority,
            "ai_analysis":      ai_resp.output,
            "ip_fingerprint":   problem_fingerprint,
            "ip_protected":     True,
            "next_actions":  [
                "Post to Global Problems Board",
                "Invite collaborators to discuss",
                "Browse existing solutions for matches",
            ],
        }

    # ── AI PROBLEM ANALYSIS ────────────────────────────────────────────────

    async def analyze_problem(
        self, user_context, problem_id: str, problem_data: Dict
    ) -> Dict[str, Any]:
        """
        POST /api/v1/solutions/problems/{id}/analyze -- 2 credits, Builder+

        Deep AI analysis: expands scope, adds missing context,
        generates stakeholder map, identifies root causes.
        """
        from ai_router_core import AIRequest, TaskType

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.PROBLEM_ANALYSIS,
            user_context=user_context,
            input_data=problem_data,
            max_tokens=4000,
            ip_protected=True,  # Deep problem analysis contains proprietary context
        ))
        return {
            "problem_id":          problem_id,
            "expanded_scope":      resp.output,
            "credits_consumed":    resp.credits_consumed,
        }

    # ── PROBLEM DISCOVERY ──────────────────────────────────────────────────

    async def discover_problems(
        self, user_context, region: Optional[str] = None,
        categories: Optional[List[str]] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """
        GET /api/v1/solutions/problems/discover -- 2 credits, Builder+

        Runs the automated Problem Discovery Engine and returns
        AI-discovered problems for review and activation.
        """
        from ai_router_core import AIRequest, TaskType

        cat_enums = [ProblemCategory(c) for c in (categories or []) if c in [e.value for e in ProblemCategory]]
        raw = self.discovery.discover(region, cat_enums or None, limit)

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.PROBLEM_DISCOVERY,
            user_context=user_context,
            input_data={"signals": raw, "region": region},
            max_tokens=3000,
        ))

        return {
            "discovered_count": len(raw),
            "problems":         raw,
            "ai_summary":       resp.output,
            "source_types":     list({p.get("source") for p in raw}),
        }

    # ── DISCUSSION ─────────────────────────────────────────────────────────

    async def add_contribution(
        self, user_context, thread_id: str,
        problem_id: str, content: str,
        contribution_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/discussions/{id}/contribute -- 1 credit, Free+"""
        ct = (ContributionType(contribution_type)
              if contribution_type in [e.value for e in ContributionType]
              else self.moderator.classify_contribution(content))

        contribution = DiscussionContribution(
            thread_id=thread_id, problem_id=problem_id,
            author_id=user_context.user_id,
            contribution_type=ct, content=content,
        )
        return {
            "contribution_id":   contribution.contribution_id,
            "classified_as":     ct.value,
            "ai_quality_score":  round(min(100.0, len(content) / 5), 1),
        }

    async def get_discussion_summary(
        self, user_context, thread_id: str,
        contributions: List[DiscussionContribution]
    ) -> Dict[str, Any]:
        """GET /api/v1/solutions/discussions/{id}/summary -- 1 credit, Free+"""
        from ai_router_core import AIRequest, TaskType

        direction = self.moderator.detect_strongest_direction(contributions)
        clusters  = self.moderator.cluster_contributions(contributions)

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.DISCUSSION_MODERATION,
            user_context=user_context,
            input_data={
                "thread_id":       thread_id,
                "contributions":   [{"type": c.contribution_type.value, "content": c.content}
                                    for c in contributions[:30]],
                "direction":       direction,
            },
            max_tokens=2000,
        ))

        return {
            "thread_id":          thread_id,
            "ai_summary":         resp.output,
            "strongest_direction": direction,
            "idea_clusters":      clusters,
            "ready_to_convert":   direction["ready_to_convert"],
        }

    # ── SOLUTION PROJECT ───────────────────────────────────────────────────

    async def convert_to_solution(
        self,
        user_context,
        problem_id:   str,
        title:        str,
        solution_type: str,
        funding_type:  str,
        description:  str,
        discussion_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/solutions/discussions/{id}/convert -- 3 credits, Founder Pro+

        Converts a matured discussion into a Solution Project.
        Runs AI solution synthesis to structure the best direction.
        """
        from ai_router_core import AIRequest, TaskType

        st = SolutionType(solution_type) if solution_type in [e.value for e in SolutionType] else SolutionType.HYBRID
        ft = FundingType(funding_type) if funding_type in [e.value for e in FundingType] else FundingType.HYBRID

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.SOLUTION_SYNTHESIS,
            user_context=user_context,
            input_data={
                "problem_id":        problem_id,
                "title":             title,
                "solution_type":     solution_type,
                "funding_type":      funding_type,
                "description":       description,
                "discussion_summary": discussion_summary or "",
            },
            max_tokens=4000,
            ip_protected=True,  # Solution blueprints are core proprietary IP
        ))

        solution = SolutionProject(
            problem_id=problem_id, title=title,
            description=description, solution_type=st,
            funding_type=ft, stage=SolutionStage.VALIDATED,
            created_by=user_context.user_id,
        )

        return {
            "solution_id":        solution.solution_id,
            "title":              solution.title,
            "solution_type":      st.value,
            "stage":              solution.stage.value,
            "ai_synthesis":       resp.output,
            "next_steps": [
                "Define execution plan",
                "Identify required roles",
                "Estimate cost and timeline",
                "Apply for grants if non-profit",
                "Begin deployment planning",
            ],
        }

    async def run_feasibility_estimate(
        self, user_context, solution_id: str, solution_data: Dict
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/projects/{id}/feasibility -- 2 credits, Builder+"""
        from ai_router_core import AIRequest, TaskType

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.FEASIBILITY_ESTIMATE,
            user_context=user_context,
            input_data=solution_data,
            max_tokens=3000,
            ip_protected=True,  # Feasibility data includes proprietary cost/technical details
        ))
        return {"solution_id": solution_id, "feasibility_report": resp.output,
                "credits_consumed": resp.credits_consumed}

    async def predict_impact(
        self, user_context, solution: SolutionProject,
        people_affected_millions: float = 1.0,
        severity: float = 7.0, scalability: float = 6.0,
        sustainability: float = 6.0, measurability: float = 7.0
    ) -> Dict[str, Any]:
        """GET /api/v1/solutions/projects/{id}/impact -- 1 credit, Free+"""
        from ai_router_core import AIRequest, TaskType

        impact = self.impact_engine.compute_impact_score(
            people_affected_millions, severity, scalability, sustainability, measurability
        )
        resp = await self.brain.process(AIRequest(
            task_type=TaskType.IMPACT_PREDICTION,
            user_context=user_context,
            input_data={"solution_title": solution.title,
                        "solution_type": solution.solution_type.value,
                        "impact_scores": impact},
            max_tokens=2000,
        ))
        return {**impact, "narrative": resp.output,
                "solution_id": solution.solution_id}

    # ── DEPLOYMENT ─────────────────────────────────────────────────────────

    async def create_deployment(
        self, user_context, solution: SolutionProject,
        mode: str, region: str, beneficiaries_target: int
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/deployments/create -- 2 credits, Founder Pro+"""
        from ai_router_core import AIRequest, TaskType

        dm = DeploymentMode(mode) if mode in [e.value for e in DeploymentMode] else DeploymentMode.PILOT_PROGRAM
        readiness = self.deployment.compute_deployment_readiness(solution)

        if not readiness["ready_to_deploy"]:
            return {"error": "Solution not ready for deployment",
                    "readiness": readiness, "missing": readiness["missing"]}

        deployment_plan = self.deployment.create_deployment_plan(
            solution, dm, region, beneficiaries_target
        )

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.DEPLOYMENT_PLANNING,
            user_context=user_context,
            input_data={"solution_title": solution.title,
                        "mode": mode, "region": region,
                        "beneficiaries_target": beneficiaries_target,
                        "checklist_count": len(deployment_plan.deployment_checklist)},
            max_tokens=2000,
            ip_protected=True,  # Deployment plans contain proprietary execution strategy
        ))

        return {
            "deployment_id":      deployment_plan.deployment_id,
            "mode":               dm.value,
            "region":             region,
            "status":             deployment_plan.status.value,
            "checklist":          deployment_plan.deployment_checklist,
            "ai_deployment_plan": resp.output,
            "readiness":          readiness,
        }

    async def submit_field_feedback(
        self, user_context, deployment_id: str, solution_id: str,
        field_report: str, impact_metrics: Dict, failure_points: List[str]
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/deployments/{id}/feedback -- 1 credit, Free+"""
        from ai_router_core import AIRequest, TaskType

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.FIELD_FEEDBACK_ANALYSIS,
            user_context=user_context,
            input_data={"field_report": field_report,
                        "impact_metrics": impact_metrics,
                        "failure_points": failure_points},
            max_tokens=2000,
        ))

        feedback = FieldFeedback(
            deployment_id=deployment_id, solution_id=solution_id,
            submitted_by=user_context.user_id,
            field_report=field_report, impact_metrics=impact_metrics,
            failure_points=failure_points, ai_analysis=resp.output,
        )
        return {"feedback_id": feedback.feedback_id,
                "ai_analysis": resp.output,
                "what_worked": feedback.what_worked,
                "loop_closed": True}

    # ── GRANTS & FUNDING ───────────────────────────────────────────────────

    async def generate_grant_application(
        self, user_context, solution: SolutionProject,
        funder_name: str, funding_type: str,
        amount_usd: float
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/grants/generate -- 3 credits, Founder Pro+"""
        from ai_router_core import AIRequest, TaskType

        resp = await self.brain.process(AIRequest(
            task_type=TaskType.GRANT_MATCHING,
            user_context=user_context,
            input_data={
                "solution_title":  solution.title,
                "solution_type":   solution.solution_type.value,
                "impact_score":    solution.impact_score,
                "funder_name":     funder_name,
                "funding_type":    funding_type,
                "amount_requested": amount_usd,
                "execution_plan":  solution.execution_plan,
            },
            max_tokens=5000,
            ip_protected=True,  # Grant applications contain confidential financial strategy
        ))

        grant = GrantApplication(
            solution_id=solution.solution_id, funder_name=funder_name,
            funding_type=FundingType(funding_type) if funding_type in [e.value for e in FundingType] else FundingType.GRANTS,
            amount_requested_usd=amount_usd,
            application_text=resp.output,
        )
        return {"application_id": grant.application_id,
                "funder":         funder_name,
                "amount_usd":     amount_usd,
                "application_text": resp.output,
                "status":         "draft",
                "export_ready":   True}

    # ── GLOBAL IMPACT DASHBOARD ────────────────────────────────────────────

    def get_global_impact_dashboard(
        self,
        active_problems:    int,
        active_solutions:   int,
        active_deployments: int,
        total_beneficiaries: int,
        countries:          List[str],
        funds_deployed_usd: float,
    ) -> Dict[str, Any]:
        """
        GET /api/v1/solutions/impact/global -- 0 credits, Free+

        Real-time global impact metrics for the platform homepage
        and government/NGO dashboards.
        """
        return {
            "headline_metrics": {
                "problems_being_solved":   active_problems,
                "active_solutions":        active_solutions,
                "active_deployments":      active_deployments,
                "people_impacted":         total_beneficiaries,
                "countries_involved":      len(countries),
                "funds_deployed_usd":      funds_deployed_usd,
            },
            "countries":       sorted(countries),
            "platform_mission": "The place where problems meet intelligence, and solutions get built.",
            "serves": [
                "Startup founders", "NGOs", "Governments",
                "Researchers", "Communities", "Corporations (CSR)",
            ],
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_idea_solution_hub() -> None:
    """Demonstrates the full Problem-Driven pathway."""

    engine = ImpactScoringEngine()

    # Compute impact for a healthcare problem in rural Africa
    impact = engine.compute_impact_score(
        people_affected_millions=50.0,
        severity=8.5,
        scalability=7.0,
        sustainability=6.5,
        measurability=8.0,
    )
    priority = engine.compute_priority_score(
        impact["impact_score"],
        ProblemUrgency.CRITICAL,
        funding_availability=7.0,
        political_feasibility=6.0,
        time_sensitivity=8.5,
    )

    print("=" * 65)
    print("TECHIT -- IDEA & SOLUTION HUB DEMO")
    print("=" * 65)
    print(f"\n📊 Impact Score:   {impact['impact_score']} -- {impact['classification']}")
    print(f"🎯 Priority Score: {priority['priority_score']} {priority['colour']} {priority['label']}")

    # Discovery engine
    discovery = ProblemDiscoveryEngine()
    found     = discovery.discover(region="Africa", limit=3)
    print(f"\n🔍 Auto-discovered problems: {len(found)}")
    for p in found:
        print(f"   • {p['title']}  [{p['category']}]  urgency={p['urgency']}")

    # Deployment engine
    solution  = SolutionProject(
        problem_id="prob_001", title="Rural Cold Storage Network",
        description="Community-operated cold storage infrastructure for smallholder farmers.",
        solution_type=SolutionType.SOCIAL_INITIATIVE,
        funding_type=FundingType.GRANTS,
        stage=SolutionStage.VALIDATED,
        execution_plan="Phase 1: pilot 3 villages; Phase 2: NGO rollout",
        required_roles=[ContributorRole.ENGINEER, ContributorRole.FIELD_OPERATOR, ContributorRole.NGO_PARTNER],
        impact_score=impact["impact_score"],
        feasibility_score=72.0,
    )
    deploy_engine = DeploymentEngine()
    readiness     = deploy_engine.compute_deployment_readiness(solution)
    print(f"\n🚀 Deployment Readiness: {readiness['readiness_score']}%  ready={readiness['ready_to_deploy']}")

    # Matching engine
    matcher = SolutionMatchingEngine()
    matches = matcher.find_matches(
        problem=ProblemNode(
            title="Post-harvest storage", category=ProblemCategory.AGRICULTURE, urgency=ProblemUrgency.HIGH
        ),
        existing_solutions=[solution],
    )
    print(f"\n🤝 Solution matches found: {len(matches)}")
    for m in matches:
        print(f"   • {m['solution_title']}  match={m['match_score']}%  reusable={m['can_reuse']}")

    print("=" * 65)


if __name__ == "__main__":
    example_idea_solution_hub()
