"""
TECHIT -- ADAPTIVE TRAINING MODULE SYSTEM
==========================================
Module: training_module.py
Layer:  Learning Intelligence Layer

Design Philosophy
─────────────────
The training system is NOT a fixed 12-week bootcamp.

It is a living curriculum engine that adapts to where a founder
actually is -- not where a schedule assumes they should be.

Duration is derived from the learner's time-to-MVP estimate,
project stage, role, available hours per week, and pace.
No two founders receive the same plan. No plan is fixed to a calendar.

Two Curriculum Zones
────────────────────
ZONE 1 -- PRE-MVP
  Everything needed to go from idea -> first live product.
  Duration: computed dynamically from time-to-MVP.
  Goal: shippable MVP with market validation.

  Tracks:
    Founder   -- Strategy, validation, business model, fundraising
    Builder   -- Technical execution, architecture, dev workflow
    Investor  -- Deal evaluation, due diligence, portfolio
    Hybrid    -- Founder who is also the primary builder

ZONE 2 -- POST-MVP
  Everything needed to grow, scale, and operate after launching.
  Triggered automatically when:
    - Market Readiness stage advances past "MVP"
    - User marks MVP as shipped (mvp_shipped event)
    - Revenue goes live (revenue_went_live event)
    - Investor expresses interest (investor_expressed_interest event)

  Tracks:
    Growth      -- User acquisition, retention, CAC/LTV
    Revenue     -- Monetisation engineering, pricing iteration
    Fundraising -- Pitch, investor targeting, term sheets
    Scale       -- Team building, infrastructure, international
    Operations  -- Compliance, governance, legal, processes

Time-to-MVP Engine
──────────────────
  Modules are expressed as Phase + Priority + Estimated Hours + Unlock Condition.
  NOT as "Week 1", "Week 2", etc.

  Duration computed from:
    hours_available_per_week × learning_pace_factor × complexity_modifier

Adaptive Triggers
─────────────────
  pivot_detected            -> re-trigger validation modules
  mvp_shipped               -> activate full post-MVP curriculum
  revenue_went_live         -> unlock revenue optimisation track
  investor_expressed_interest -> fast-track fundraising modules
  evi_dropped               -> surface execution discipline modules
  unicorn_score_below_50    -> elevate validation to critical
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# ENUMERATIONS
# ============================================================================

class TrainingZone(Enum):
    PRE_MVP  = "pre_mvp"
    POST_MVP = "post_mvp"


class TrainingTrack(Enum):
    # Pre-MVP
    FOUNDER     = "founder"
    BUILDER     = "builder"
    INVESTOR    = "investor"
    HYBRID      = "hybrid"
    # Post-MVP
    GROWTH      = "growth"
    REVENUE     = "revenue"
    FUNDRAISING = "fundraising"
    SCALE       = "scale"
    OPERATIONS  = "operations"


class TrainingPhase(Enum):
    VALIDATION = "validation"
    BUILD      = "build"
    LAUNCH     = "launch"
    GROW       = "grow"
    OPTIMISE   = "optimise"
    RAISE      = "raise"
    SCALE_UP   = "scale_up"
    GOVERN     = "govern"


class ModulePriority(Enum):
    CRITICAL  = "critical"   # blocks next phase if missed
    IMPORTANT = "important"
    OPTIONAL  = "optional"


class ModuleFormat(Enum):
    VIDEO      = "video"
    AUDIO      = "audio"
    READING    = "reading"
    EXERCISE   = "exercise"
    WORKSHOP   = "workshop"
    ASSESSMENT = "assessment"
    TEMPLATE   = "template"
    SIMULATION = "simulation"


class LearningPace(Enum):
    INTENSIVE = "intensive"   # 3+ hours/day -- 40% faster
    STANDARD  = "standard"   # 1–2 hours/day
    PART_TIME = "part_time"  # < 1 hour/day -- 80% slower


class UnlockTrigger(Enum):
    ALWAYS_OPEN        = "always_open"
    PREVIOUS_COMPLETE  = "previous_complete"
    UNICORN_SCORE_MIN  = "unicorn_score_min"
    STAGE_REACHED      = "stage_reached"
    BETA_USERS_MIN     = "beta_users_min"
    REVENUE_LIVE       = "revenue_live"
    INVESTOR_INTEREST  = "investor_interest"
    TEAM_SIZE_MIN      = "team_size_min"
    TUTOR_APPROVED     = "tutor_approved"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class UnlockCondition:
    trigger:            UnlockTrigger
    threshold:          Optional[float] = None
    stage_required:     Optional[str]   = None
    prereq_module_ids:  List[str]       = field(default_factory=list)


@dataclass
class CompletionCriteria:
    requires_quiz:        bool  = False
    min_quiz_score_pct:   float = 70.0
    requires_exercise:    bool  = False
    exercise_description: str   = ""
    requires_ai_review:   bool  = False
    self_reported_ok:     bool  = True


@dataclass
class TrainingModule:
    """
    One atomic learning unit. Not tied to a week number.
    Duration = estimated_hours. Sequence = phase + priority + prerequisites.
    """
    module_id:              str
    title:                  str
    description:            str
    learning_objective:     str
    zone:                   TrainingZone
    track:                  TrainingTrack
    phase:                  TrainingPhase
    priority:               ModulePriority
    estimated_hours:        float
    formats:                List[ModuleFormat]
    unlock_conditions:      List[UnlockCondition]
    completion_criteria:    CompletionCriteria
    tags:                   List[str]
    ai_tutor_context:       str                    = ""
    certification_contribution: bool               = False
    resources:              List[str]              = field(default_factory=list)
    tools_used:             List[str]              = field(default_factory=list)


@dataclass
class LearnerProfile:
    user_id:                  str
    role:                     str
    industry:                 str
    project_stage:            str
    hours_available_per_week: float
    learning_pace:            LearningPace
    target_mvp_weeks:         int
    has_technical_skills:     bool
    team_size:                int
    has_cofounder:            bool
    pre_existing_skills:      List[str]
    unicorn_score:            float
    current_stage:            str
    beta_users_count:         int
    has_revenue:              bool
    investor_interest:        bool


@dataclass
class PersonalisedCurriculum:
    curriculum_id:            str          = field(default_factory=lambda: str(uuid.uuid4()))
    learner_profile:          Optional[LearnerProfile] = None
    pre_mvp_modules:          List[TrainingModule] = field(default_factory=list)
    estimated_weeks_to_mvp:   float        = 0.0
    estimated_hours_to_mvp:   float        = 0.0
    post_mvp_tracks_available: List[TrainingTrack] = field(default_factory=list)
    post_mvp_modules_unlocked: List[TrainingModule] = field(default_factory=list)
    post_mvp_modules_locked:   List[TrainingModule] = field(default_factory=list)
    completed_module_ids:     List[str]    = field(default_factory=list)
    next_module:              Optional[TrainingModule] = None
    certifications_eligible:  List[str]    = field(default_factory=list)
    generated_at:             datetime     = field(default_factory=datetime.utcnow)
    last_adapted_at:          Optional[datetime] = None
    adaptation_reason:        Optional[str]      = None


# ============================================================================
# MODULE LIBRARY -- 37 CANONICAL MODULES
# ============================================================================

class ModuleLibrary:
    """
    Complete TechIT module library. Modules are canonical -- composed into
    personalised curricula dynamically. Adding a module here makes it
    immediately available to the curriculum engine.
    """

    # ── PRE-MVP / FOUNDER / VALIDATION ────────────────────────────────────

    @staticmethod
    def pre_mvp_founder_validation() -> List[TrainingModule]:
        return [
            TrainingModule(
                "fv_001", "Problem Clarity Framework",
                "Define the exact problem you are solving and who suffers from it most.",
                "Write a crisp 2-sentence problem statement that any investor can understand.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.ALWAYS_OPEN)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your 2-sentence problem statement for AI review."),
                ["problem-definition", "market-fit", "early-stage"],
                ai_tutor_context="Teach Jobs-to-be-Done and Mom Test for problem definition.",
                certification_contribution=True, tools_used=["Notion template"],
            ),
            TrainingModule(
                "fv_002", "Customer Discovery Interviews",
                "Conduct structured interviews to validate the problem is real and worth solving.",
                "Conduct 10 customer interviews using a validated script and synthesise findings.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 3.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit notes from at least 5 real customer conversations.",
                    requires_ai_review=True),
                ["customer-discovery", "validation", "mom-test"],
                ai_tutor_context="Teach Mom Test methodology and how to avoid confirmation bias.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fv_003", "Market Size Estimation (TAM/SAM/SOM)",
                "Estimate the opportunity using bottom-up and top-down methods.",
                "Produce a credible TAM/SAM/SOM calculation that withstands investor scrutiny.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete the TAM/SAM/SOM spreadsheet with cited sources."),
                ["market-sizing", "tam-sam-som", "investor-ready"],
                ai_tutor_context="Explain bottom-up vs top-down sizing. Show how to cite sources.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fv_004", "Competitive Landscape Analysis",
                "Map direct and indirect competitors and identify your defensible wedge.",
                "Complete a competitor matrix and articulate your unfair advantage in one sentence.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.IMPORTANT, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_003"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete the competitive matrix and differentiation statement."),
                ["competition", "differentiation", "moat"],
                ai_tutor_context="Teach 2x2 competitive matrix. Explain genuine moat vs temporary advantage.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fv_005", "Unicorn Score Deep Dive",
                "Understand your GSIS and Unicorn score and how to improve each driver.",
                "Identify your 3 lowest unicorn drivers and create a 30-day improvement plan.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.IMPORTANT, 1.0,
                [ModuleFormat.VIDEO, ModuleFormat.READING, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.ALWAYS_OPEN)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Write a 1-page improvement plan for your 3 weakest drivers."),
                ["unicorn-model", "scoring", "gsis"],
                ai_tutor_context="Explain the 10 unicorn drivers and how GSIS aggregates them.",
                certification_contribution=False,
            ),
            TrainingModule(
                "fv_006", "Revenue Model Design",
                "Choose and validate the right revenue model for your market.",
                "Select your primary and secondary revenue models with supporting rationale.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.WORKSHOP, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_002"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete the Revenue Model Canvas.",
                    requires_ai_review=True),
                ["revenue-model", "monetisation", "pricing"],
                ai_tutor_context="Cover SaaS, marketplace, freemium, transactional, usage-based models.",
                certification_contribution=True,
            ),
        ]

    # ── PRE-MVP / FOUNDER / BUILD ──────────────────────────────────────────

    @staticmethod
    def pre_mvp_founder_build() -> List[TrainingModule]:
        return [
            TrainingModule(
                "fb_001", "Defining Your MVP Scope",
                "Determine the absolute minimum feature set that proves your core hypothesis.",
                "Write an MVP definition doc with features to build, cut, and success criteria.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_002", "fv_006"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your MVP Definition Document for AI review.",
                    requires_ai_review=True),
                ["mvp", "product-scope", "lean-startup"],
                ai_tutor_context="Teach lean startup MVP concept. Help founders cut features ruthlessly.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fb_002", "Go-to-Market Strategy Foundations",
                "Build the GTM plan that will get your first 100 users.",
                "Produce a written GTM plan with channels, messaging, ICP, and 90-day targets.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_004"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete the GTM Strategy Canvas.",
                    requires_ai_review=True),
                ["gtm", "user-acquisition", "marketing"],
                ai_tutor_context="Cover ICP, channel selection, messaging, B2B vs B2C acquisition.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fb_003", "Unit Economics Fundamentals",
                "Calculate the core financial metrics that determine if your model is viable.",
                "Calculate projected CAC, LTV, payback period, and gross margin.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.BUILD,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fv_006"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete the Unit Economics spreadsheet with assumptions."),
                ["unit-economics", "cac", "ltv", "saas-metrics"],
                ai_tutor_context="Explain CAC, LTV, LTV:CAC ratio, payback period, churn, gross margin.",
                certification_contribution=True, tools_used=["Unit economics spreadsheet"],
            ),
        ]

    # ── PRE-MVP / FOUNDER / LAUNCH ─────────────────────────────────────────

    @staticmethod
    def pre_mvp_founder_launch() -> List[TrainingModule]:
        return [
            TrainingModule(
                "fl_001", "Beta Testing Strategy",
                "Design and execute a structured beta program that generates actionable feedback.",
                "Launch a beta program with 50+ users and systematic feedback collection.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.LAUNCH,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fb_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your beta testing plan and feedback survey design."),
                ["beta", "user-testing", "feedback-loops"],
                ai_tutor_context="Teach NPS, CSAT, qualitative feedback frameworks, structured beta cohorts.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fl_002", "Launch Narrative and Positioning",
                "Craft the story that makes your launch memorable and shareable.",
                "Write your positioning statement, tagline, and launch narrative.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.LAUNCH,
                ModulePriority.IMPORTANT, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["fb_002"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit positioning statement and tagline for AI review.",
                    requires_ai_review=True),
                ["positioning", "messaging", "launch", "storytelling"],
                ai_tutor_context="Teach April Dunford's positioning framework and before/after/bridge narrative.",
                certification_contribution=True,
            ),
            TrainingModule(
                "fl_003", "Pre-Launch Founder Certification Assessment",
                "Final assessment covering validation through launch readiness.",
                "Pass the comprehensive pre-launch assessment with ≥75% score.",
                TrainingZone.PRE_MVP, TrainingTrack.FOUNDER, TrainingPhase.LAUNCH,
                ModulePriority.CRITICAL, 1.0,
                [ModuleFormat.ASSESSMENT],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE,
                    prereq_module_ids=["fl_001", "fl_002", "fb_003"])],
                CompletionCriteria(requires_quiz=True, min_quiz_score_pct=75.0, self_reported_ok=False),
                ["assessment", "certification", "launch-readiness"],
                ai_tutor_context="TechIT Founder Pre-Launch Certification. Grade rigorously.",
                certification_contribution=True,
            ),
        ]

    # ── PRE-MVP / BUILDER ──────────────────────────────────────────────────

    @staticmethod
    def pre_mvp_builder() -> List[TrainingModule]:
        return [
            TrainingModule(
                "bv_001", "Technical Problem Scoping",
                "Translate a business problem into a technical architecture question.",
                "Write a technical scoping document mapping user needs to system requirements.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.ALWAYS_OPEN)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your technical scoping document."),
                ["requirements", "technical-scoping", "architecture"],
                ai_tutor_context="Teach requirements gathering, user stories, business-to-system translation.",
                certification_contribution=True,
            ),
            TrainingModule(
                "bv_002", "Tech Stack Selection for Startups",
                "Choose a stack that lets you move fast and scale later.",
                "Select and justify a tech stack for your specific use case.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.READING, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["bv_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit stack selection with rationale for each layer."),
                ["tech-stack", "architecture", "scalability"],
                ai_tutor_context="Cover frontend/backend/db selection. PostgreSQL vs NoSQL. Monolith vs microservices.",
                certification_contribution=True,
            ),
            TrainingModule(
                "bb_001", "MVP Architecture Patterns",
                "Design a lean, extensible architecture that ships fast without fatal technical debt.",
                "Draw and describe your MVP system architecture diagram.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE, ModuleFormat.WORKSHOP],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["bv_002"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your architecture diagram for AI review.",
                    requires_ai_review=True),
                ["architecture", "mvp", "system-design"],
                ai_tutor_context="Teach modular monolith for MVPs. Service boundaries, API design, DB schema.",
                certification_contribution=True, tools_used=["draw.io", "Excalidraw"],
            ),
            TrainingModule(
                "bb_002", "Authentication and Security Foundations",
                "Implement auth correctly from day one -- mistakes here follow you forever.",
                "Implement JWT-based auth with role-based access control.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["bb_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit auth implementation for code review."),
                ["security", "authentication", "jwt", "rbac"],
                ai_tutor_context="JWT vs session auth, password hashing, RBAC, OWASP top 10.",
                certification_contribution=True,
            ),
            TrainingModule(
                "bb_003", "Database Design and Migrations",
                "Design a schema that supports your business model and evolves without pain.",
                "Write production-grade migrations with rollback support.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["bb_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit schema and at least one reversible migration file."),
                ["database", "postgresql", "migrations", "schema-design"],
                ai_tutor_context="Normalisation, indexing strategy, Alembic migrations, pgvector for AI.",
                certification_contribution=True, tools_used=["PostgreSQL", "Alembic", "pgvector"],
            ),
            TrainingModule(
                "bb_004", "CI/CD and Deployment Fundamentals",
                "Ship code with confidence -- automated tests, containers, pipelines.",
                "Set up a CI/CD pipeline that tests and deploys on push.",
                TrainingZone.PRE_MVP, TrainingTrack.BUILDER, TrainingPhase.BUILD,
                ModulePriority.IMPORTANT, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["bb_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit a working GitHub Actions workflow file."),
                ["ci-cd", "docker", "deployment", "devops"],
                ai_tutor_context="Docker basics, GitHub Actions, staging vs production, rollback strategies.",
                certification_contribution=False, tools_used=["Docker", "GitHub Actions"],
            ),
        ]

    # ── PRE-MVP / INVESTOR ─────────────────────────────────────────────────

    @staticmethod
    def pre_mvp_investor() -> List[TrainingModule]:
        return [
            TrainingModule(
                "iv_001", "Deal Flow Evaluation Framework",
                "Build a repeatable framework for evaluating startup opportunities fast.",
                "Create and apply a deal evaluation scorecard to 5 startups.",
                TrainingZone.PRE_MVP, TrainingTrack.INVESTOR, TrainingPhase.VALIDATION,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.ALWAYS_OPEN)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit scorecard and evaluations of 5 startups."),
                ["deal-flow", "evaluation", "due-diligence", "venture"],
                ai_tutor_context="Sequoia, YC, First Round evaluation frameworks. Market, team, traction, defensibility.",
                certification_contribution=True,
            ),
            TrainingModule(
                "iv_002", "Due Diligence Execution",
                "Conduct thorough DD without wasting a founder's time or your own.",
                "Complete a full DD checklist for one real or simulated startup.",
                TrainingZone.PRE_MVP, TrainingTrack.INVESTOR, TrainingPhase.BUILD,
                ModulePriority.CRITICAL, 3.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.SIMULATION],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["iv_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit a completed DD report on a simulated startup.",
                    requires_ai_review=True),
                ["due-diligence", "risk-assessment", "legal", "financial-review"],
                ai_tutor_context="Financial DD, legal review, reference checks, technical architecture review.",
                certification_contribution=True,
            ),
        ]

    # ── POST-MVP / GROWTH ──────────────────────────────────────────────────

    @staticmethod
    def post_mvp_growth() -> List[TrainingModule]:
        return [
            TrainingModule(
                "pg_001", "Retention Engineering",
                "Stop losing users before fixing acquisition. Retention is the foundation of growth.",
                "Identify your primary retention lever and implement one improvement this week.",
                TrainingZone.POST_MVP, TrainingTrack.GROWTH, TrainingPhase.GROW,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.STAGE_REACHED, stage_required="beta")],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your retention analysis and improvement plan."),
                ["retention", "churn", "product-market-fit", "activation"],
                ai_tutor_context="Retention curve, activation events, habit loops, onboarding and retention link.",
                certification_contribution=True,
            ),
            TrainingModule(
                "pg_002", "Growth Loops vs Funnels",
                "Funnels leak. Loops compound. Design compounding growth into your product.",
                "Map your acquisition funnel and redesign one stage as a growth loop.",
                TrainingZone.POST_MVP, TrainingTrack.GROWTH, TrainingPhase.GROW,
                ModulePriority.CRITICAL, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.WORKSHOP, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.BETA_USERS_MIN, threshold=10)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit your growth loop diagram and implementation plan.",
                    requires_ai_review=True),
                ["growth", "viral-loops", "acquisition", "product-led"],
                ai_tutor_context="Viral loops, content loops, paid loops, organic vs paid compounding.",
                certification_contribution=True,
            ),
            TrainingModule(
                "pg_003", "Analytics Setup and Instrumentation",
                "Instrument your product properly -- if you can't measure it, you can't improve it.",
                "Set up event tracking and create a metrics dashboard.",
                TrainingZone.POST_MVP, TrainingTrack.GROWTH, TrainingPhase.GROW,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.STAGE_REACHED, stage_required="mvp")],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit analytics implementation with 5+ tracked events."),
                ["analytics", "metrics", "instrumentation"],
                ai_tutor_context="Amplitude, PostHog, Mixpanel. Event taxonomy, funnel and cohort analysis.",
                certification_contribution=False, tools_used=["Amplitude", "PostHog"],
            ),
            TrainingModule(
                "pg_004", "Content and Community as Acquisition",
                "Build an audience that becomes your cheapest and most loyal acquisition channel.",
                "Publish 3 pieces of content and measure which drives the most qualified traffic.",
                TrainingZone.POST_MVP, TrainingTrack.GROWTH, TrainingPhase.GROW,
                ModulePriority.OPTIONAL, 3.0,
                [ModuleFormat.VIDEO, ModuleFormat.WORKSHOP, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.STAGE_REACHED, stage_required="launch")],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit 3 published content pieces with performance metrics."),
                ["content-marketing", "community", "seo"],
                ai_tutor_context="Content-led growth, SEO for startups, community building, content ROI.",
                certification_contribution=False,
            ),
        ]

    # ── POST-MVP / REVENUE ─────────────────────────────────────────────────

    @staticmethod
    def post_mvp_revenue() -> List[TrainingModule]:
        return [
            TrainingModule(
                "pr_001", "Pricing Strategy and Iteration",
                "Most startups underprice. Learn how to charge what your product is worth.",
                "Test two pricing structures and measure impact on conversion and revenue.",
                TrainingZone.POST_MVP, TrainingTrack.REVENUE, TrainingPhase.OPTIMISE,
                ModulePriority.CRITICAL, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.SIMULATION, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.BETA_USERS_MIN, threshold=20)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Run a pricing experiment and submit results.",
                    requires_ai_review=True),
                ["pricing", "revenue", "willingness-to-pay"],
                ai_tutor_context="Value-based pricing, price anchoring, packaging, pricing experiments.",
                certification_contribution=True,
            ),
            TrainingModule(
                "pr_002", "Revenue Model Optimisation",
                "Move from one revenue stream to a resilient, layered revenue architecture.",
                "Add a second revenue stream that increases LTV without increasing CAC.",
                TrainingZone.POST_MVP, TrainingTrack.REVENUE, TrainingPhase.OPTIMISE,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.WORKSHOP, ModuleFormat.TEMPLATE],
                [UnlockCondition(UnlockTrigger.REVENUE_LIVE)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Design second revenue stream with financial projections."),
                ["revenue-streams", "monetisation", "ltv", "arpu"],
                ai_tutor_context="Expansion revenue, upselling, cross-selling, usage-based billing.",
                certification_contribution=True,
            ),
            TrainingModule(
                "pr_003", "Financial Modelling for Operators",
                "Build the financial model that runs your business -- not just the one you show investors.",
                "Produce a rolling 12-month operating model with weekly actuals tracking.",
                TrainingZone.POST_MVP, TrainingTrack.REVENUE, TrainingPhase.OPTIMISE,
                ModulePriority.IMPORTANT, 3.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.REVENUE_LIVE)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit 12-month operating model with actuals for month 1."),
                ["financial-modelling", "burn-rate", "forecasting"],
                ai_tutor_context="Operating vs fundraising model. Revenue recognition, accruals, cash flow.",
                certification_contribution=True, tools_used=["Google Sheets template"],
            ),
        ]

    # ── POST-MVP / FUNDRAISING ─────────────────────────────────────────────

    @staticmethod
    def post_mvp_fundraising() -> List[TrainingModule]:
        return [
            TrainingModule(
                "pf_001", "Investor Targeting and Research",
                "Find the 20 investors most likely to fund your startup -- and ignore the rest.",
                "Build a targeted pipeline of 20 qualified investors with personalised outreach.",
                TrainingZone.POST_MVP, TrainingTrack.FUNDRAISING, TrainingPhase.RAISE,
                ModulePriority.CRITICAL, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.INVESTOR_INTEREST)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit investor pipeline spreadsheet with 20 qualified prospects."),
                ["fundraising", "investor-relations", "outreach"],
                ai_tutor_context="Crunchbase, AngelList, LinkedIn for investor research. Stage, sector, geography fit.",
                certification_contribution=True, tools_used=["Crunchbase", "AngelList"],
            ),
            TrainingModule(
                "pf_002", "Pitch Deck Construction",
                "Build the 10-slide deck that gets you the meeting -- not the 40-slide deck that loses it.",
                "Produce a complete, investor-grade pitch deck that passes AI review.",
                TrainingZone.POST_MVP, TrainingTrack.FUNDRAISING, TrainingPhase.RAISE,
                ModulePriority.CRITICAL, 3.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE, ModuleFormat.SIMULATION],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["pf_001"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit pitch deck for AI scoring and feedback.",
                    requires_ai_review=True),
                ["pitch-deck", "fundraising", "storytelling"],
                ai_tutor_context="Sequoia pitch deck structure. Score: problem, solution, market, traction, team, ask.",
                certification_contribution=True, tools_used=["Pitch template", "Canva"],
            ),
            TrainingModule(
                "pf_003", "Term Sheet Literacy",
                "Understand what you sign before you sign it -- dilution, pro-rata, control rights.",
                "Read and explain every standard clause in a seed-stage term sheet.",
                TrainingZone.POST_MVP, TrainingTrack.FUNDRAISING, TrainingPhase.RAISE,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.READING, ModuleFormat.SIMULATION],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["pf_002"])],
                CompletionCriteria(requires_quiz=True, min_quiz_score_pct=70.0),
                ["term-sheet", "legal", "dilution", "cap-table"],
                ai_tutor_context="Pre/post-money valuation, pro-rata, anti-dilution, board, drag-along in plain English.",
                certification_contribution=True,
            ),
            TrainingModule(
                "pf_004", "Investor Data Room",
                "Build the data room that accelerates due diligence and builds trust.",
                "Assemble a complete investor data room with all standard documents.",
                TrainingZone.POST_MVP, TrainingTrack.FUNDRAISING, TrainingPhase.RAISE,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.PREVIOUS_COMPLETE, prereq_module_ids=["pf_002"])],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Set up data room with at least 8 of 12 standard documents.",
                    requires_ai_review=True),
                ["data-room", "due-diligence", "transparency"],
                ai_tutor_context="12 standard data room documents. What investors look for. Common red flags.",
                certification_contribution=True, tools_used=["Notion", "Google Drive", "Docsend"],
            ),
        ]

    # ── POST-MVP / SCALE ───────────────────────────────────────────────────

    @staticmethod
    def post_mvp_scale() -> List[TrainingModule]:
        return [
            TrainingModule(
                "ps_001", "Hiring Your First 10 Employees",
                "The first 10 hires define your culture for years. Get this right.",
                "Write a hiring plan with role prioritisation, scorecards, and interview process.",
                TrainingZone.POST_MVP, TrainingTrack.SCALE, TrainingPhase.SCALE_UP,
                ModulePriority.CRITICAL, 2.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.WORKSHOP],
                [UnlockCondition(UnlockTrigger.TEAM_SIZE_MIN, threshold=3)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit hiring plan and at least one role scorecard."),
                ["hiring", "team-building", "culture", "org-design"],
                ai_tutor_context="Who method by Geoff Smart. Culture fit vs add. Structured interview process.",
                certification_contribution=True, tools_used=["Notion hiring tracker"],
            ),
            TrainingModule(
                "ps_002", "Infrastructure Scaling Fundamentals",
                "Prepare your infrastructure for 10x the current load before you need it.",
                "Identify three scaling bottlenecks and create a mitigation plan.",
                TrainingZone.POST_MVP, TrainingTrack.SCALE, TrainingPhase.SCALE_UP,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.BETA_USERS_MIN, threshold=100)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit scaling bottleneck analysis and remediation plan."),
                ["infrastructure", "scaling", "performance", "devops"],
                ai_tutor_context="Horizontal vs vertical scaling, read replicas, Redis caching, CDN, load balancing.",
                certification_contribution=False,
            ),
        ]

    # ── POST-MVP / OPERATIONS ──────────────────────────────────────────────

    @staticmethod
    def post_mvp_operations() -> List[TrainingModule]:
        return [
            TrainingModule(
                "po_001", "Legal Entity and Compliance Foundations",
                "Get legal structure right before you raise money or hire. Mistakes are expensive.",
                "Complete legal entity setup checklist and identify outstanding compliance gaps.",
                TrainingZone.POST_MVP, TrainingTrack.OPERATIONS, TrainingPhase.GOVERN,
                ModulePriority.CRITICAL, 1.5,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.READING],
                [UnlockCondition(UnlockTrigger.STAGE_REACHED, stage_required="launch")],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Complete legal checklist and identify 3 most urgent gaps."),
                ["legal", "compliance", "entity-setup", "ip-protection"],
                ai_tutor_context="Delaware C-Corp vs LLC, IP assignment, ToS, privacy, GDPR basics.",
                certification_contribution=True,
            ),
            TrainingModule(
                "po_002", "Building Operational Systems",
                "Replace founder heroics with repeatable systems that scale without you.",
                "Document 3 core operational processes and assign ownership to team members.",
                TrainingZone.POST_MVP, TrainingTrack.OPERATIONS, TrainingPhase.GOVERN,
                ModulePriority.IMPORTANT, 2.0,
                [ModuleFormat.VIDEO, ModuleFormat.TEMPLATE, ModuleFormat.EXERCISE],
                [UnlockCondition(UnlockTrigger.TEAM_SIZE_MIN, threshold=3)],
                CompletionCriteria(requires_exercise=True,
                    exercise_description="Submit 3 documented SOPs with owners and success metrics."),
                ["operations", "systems", "sops", "delegation"],
                ai_tutor_context="EOS framework, OKRs, process documentation without over-engineering.",
                certification_contribution=False, tools_used=["Notion", "Linear", "Loom"],
            ),
        ]

    @classmethod
    def all_modules(cls) -> List[TrainingModule]:
        return (
            cls.pre_mvp_founder_validation() + cls.pre_mvp_founder_build() +
            cls.pre_mvp_founder_launch()     + cls.pre_mvp_builder()       +
            cls.pre_mvp_investor()           + cls.post_mvp_growth()       +
            cls.post_mvp_revenue()           + cls.post_mvp_fundraising()  +
            cls.post_mvp_scale()             + cls.post_mvp_operations()
        )

    @classmethod
    def by_id(cls) -> Dict[str, TrainingModule]:
        return {m.module_id: m for m in cls.all_modules()}


# ============================================================================
# TIME-TO-MVP ENGINE
# ============================================================================

class TimeToMVPEngine:
    """
    Estimates weeks to MVP from learner profile.
    This drives curriculum duration -- training compresses or expands to fit.

    Base weeks by stage -> complexity modifier -> team modifier -> pace multiplier
    """

    BASE_WEEKS: Dict[str, float] = {
        "idea": 12.0, "validation": 8.0, "mvp": 4.0,
        "beta": 2.0,  "launch": 0.0,    "growth": 0.0, "scale": 0.0,
    }

    PACE_MULT: Dict[LearningPace, float] = {
        LearningPace.INTENSIVE: 0.60,
        LearningPace.STANDARD:  1.00,
        LearningPace.PART_TIME: 1.80,
    }

    def estimate(self, profile: LearnerProfile) -> Dict[str, Any]:
        base = self.BASE_WEEKS.get(profile.current_stage, 12.0)

        complexity = (
            1.50 if not profile.has_technical_skills and not profile.has_cofounder else
            0.85 if profile.has_technical_skills else
            1.10
        )
        team_mod = 0.80 if profile.team_size >= 3 else 0.90 if profile.team_size == 2 else 1.00

        raw_weeks = float(profile.target_mvp_weeks) if profile.target_mvp_weeks > 0 else base * complexity * team_mod
        pace_mult  = self.PACE_MULT[profile.learning_pace]
        final      = round(raw_weeks * pace_mult, 1)

        weekly_target = max(2.0, profile.hours_available_per_week)
        total_hours   = round(final * weekly_target, 1)
        mvp_date      = datetime.utcnow() + timedelta(weeks=final)

        return {
            "estimated_weeks_to_mvp":       final,
            "curriculum_duration_weeks":    final,
            "estimated_total_hours":        total_hours,
            "weekly_learning_target_hours": weekly_target,
            "mvp_target_date":              mvp_date.strftime("%Y-%m-%d"),
            "learning_pace":                profile.learning_pace.value,
        }


# ============================================================================
# ADAPTIVE CURRICULUM ENGINE
# ============================================================================

class AdaptiveCurriculumEngine:
    """
    Builds and adapts personalised curricula from the module library.

    Pre-MVP priority filter by available weeks:
      < 4 weeks  -> CRITICAL only
      4–8 weeks  -> CRITICAL + IMPORTANT
      > 8 weeks  -> all three priorities

    Post-MVP module unlocking:
      Each module has conditions (stage, beta_users, revenue, investor_interest).
      Conditions evaluated against current learner state.

    Adaptation triggers handled by adapt():
      mvp_shipped, investor_expressed_interest, revenue_went_live, pivot_detected
    """

    STAGE_ORDER = ["idea", "validation", "mvp", "beta", "launch", "growth", "scale"]
    PHASE_ORDER = {
        TrainingPhase.VALIDATION: 0, TrainingPhase.BUILD: 1, TrainingPhase.LAUNCH: 2,
        TrainingPhase.GROW: 3, TrainingPhase.OPTIMISE: 4, TrainingPhase.RAISE: 5,
        TrainingPhase.SCALE_UP: 6, TrainingPhase.GOVERN: 7,
    }
    PRIORITY_ORDER = {ModulePriority.CRITICAL: 0, ModulePriority.IMPORTANT: 1, ModulePriority.OPTIONAL: 2}

    def __init__(self) -> None:
        self.time_engine = TimeToMVPEngine()
        self.library_ids = ModuleLibrary.by_id()

    def build(self, profile: LearnerProfile) -> PersonalisedCurriculum:
        c         = PersonalisedCurriculum(learner_profile=profile)
        time_data = self.time_engine.estimate(profile)

        c.pre_mvp_modules        = self._select_pre_mvp(profile, time_data)
        c.estimated_weeks_to_mvp = time_data["estimated_weeks_to_mvp"]
        c.estimated_hours_to_mvp = time_data["estimated_total_hours"]

        if profile.current_stage not in ("idea", "validation", "mvp"):
            unlocked, locked, tracks = self._build_post_mvp(profile)
            c.post_mvp_modules_unlocked  = unlocked
            c.post_mvp_modules_locked    = locked
            c.post_mvp_tracks_available  = tracks

        c.next_module = (c.pre_mvp_modules[0] if c.pre_mvp_modules else
                         (c.post_mvp_modules_unlocked[0] if c.post_mvp_modules_unlocked else None))

        role_cert_map = {
            "founder":  ["TechIT Founder -- Pre-Launch Certification",
                         "TechIT Founder -- Market-Ready Certification"],
            "builder":  ["TechIT Builder -- Technical Foundations Certification"],
            "investor": ["TechIT Investor -- Deal Evaluation Certification"],
            "hybrid":   ["TechIT Founder -- Pre-Launch Certification",
                         "TechIT Builder -- Technical Foundations Certification"],
        }
        c.certifications_eligible = role_cert_map.get(profile.role, [])
        return c

    def adapt(
        self,
        curriculum:    PersonalisedCurriculum,
        trigger_event: str,
        event_data:    Dict[str, Any],
    ) -> PersonalisedCurriculum:
        """Adapt an existing curriculum based on a platform event."""
        profile = curriculum.learner_profile

        if trigger_event == "mvp_shipped":
            unlocked, locked, tracks = self._build_post_mvp(profile, override_stage="beta")
            curriculum.post_mvp_modules_unlocked = unlocked
            curriculum.post_mvp_modules_locked   = locked
            curriculum.post_mvp_tracks_available  = tracks
            curriculum.adaptation_reason = "MVP shipped -- post-MVP curriculum activated"

        elif trigger_event == "investor_expressed_interest":
            fundraising = [m for m in curriculum.post_mvp_modules_locked
                           if m.track == TrainingTrack.FUNDRAISING]
            for m in fundraising:
                curriculum.post_mvp_modules_locked.remove(m)
                if m not in curriculum.post_mvp_modules_unlocked:
                    curriculum.post_mvp_modules_unlocked.insert(0, m)
            curriculum.adaptation_reason = "Investor interest -- fundraising track fast-tracked"

        elif trigger_event == "revenue_went_live":
            revenue_mods = [m for m in ModuleLibrary.post_mvp_revenue()
                            if m not in curriculum.post_mvp_modules_unlocked]
            curriculum.post_mvp_modules_unlocked.extend(revenue_mods)
            curriculum.adaptation_reason = "Revenue live -- revenue track unlocked"

        elif trigger_event == "pivot_detected":
            validation = [m for m in ModuleLibrary.pre_mvp_founder_validation()
                          if m.module_id not in curriculum.completed_module_ids
                          and m not in curriculum.pre_mvp_modules]
            curriculum.pre_mvp_modules = validation + curriculum.pre_mvp_modules
            curriculum.adaptation_reason = "Pivot detected -- validation modules re-prioritised"

        curriculum.last_adapted_at = datetime.utcnow()
        return curriculum

    def _select_pre_mvp(self, profile: LearnerProfile, time_data: Dict) -> List[TrainingModule]:
        weeks = time_data["estimated_weeks_to_mvp"]
        priorities = (
            {ModulePriority.CRITICAL}
            if weeks < 4 else
            {ModulePriority.CRITICAL, ModulePriority.IMPORTANT}
            if weeks <= 8 else
            {ModulePriority.CRITICAL, ModulePriority.IMPORTANT, ModulePriority.OPTIONAL}
        )
        track_map = {
            "founder":  [TrainingTrack.FOUNDER],
            "builder":  [TrainingTrack.BUILDER],
            "investor": [TrainingTrack.INVESTOR],
            "hybrid":   [TrainingTrack.FOUNDER, TrainingTrack.BUILDER],
        }
        tracks = set(track_map.get(profile.role, [TrainingTrack.FOUNDER]))

        candidates = [
            m for m in ModuleLibrary.all_modules()
            if m.zone == TrainingZone.PRE_MVP
            and m.track in tracks
            and m.priority in priorities
            and not any(tag in profile.pre_existing_skills for tag in m.tags)
        ]
        candidates.sort(key=lambda m: (
            self.PHASE_ORDER.get(m.phase, 99),
            self.PRIORITY_ORDER.get(m.priority, 99),
            m.estimated_hours,
        ))
        return candidates

    def _build_post_mvp(
        self, profile: LearnerProfile, override_stage: Optional[str] = None
    ) -> Tuple[List[TrainingModule], List[TrainingModule], List[TrainingTrack]]:
        stage    = override_stage or profile.current_stage
        unlocked: List[TrainingModule] = []
        locked:   List[TrainingModule] = []
        tracks:   List[TrainingTrack]  = []

        all_post = (
            ModuleLibrary.post_mvp_growth() + ModuleLibrary.post_mvp_revenue() +
            ModuleLibrary.post_mvp_fundraising() + ModuleLibrary.post_mvp_scale() +
            ModuleLibrary.post_mvp_operations()
        )
        for m in all_post:
            if self._check_unlock(m, profile, stage):
                unlocked.append(m)
                if m.track not in tracks:
                    tracks.append(m.track)
            else:
                locked.append(m)

        unlocked.sort(key=lambda m: (
            self.PHASE_ORDER.get(m.phase, 99),
            self.PRIORITY_ORDER.get(m.priority, 99),
        ))
        return unlocked, locked, tracks

    def _check_unlock(self, m: TrainingModule, profile: LearnerProfile, stage: str) -> bool:
        for cond in m.unlock_conditions:
            t = cond.trigger
            if t == UnlockTrigger.ALWAYS_OPEN:
                return True
            if t == UnlockTrigger.STAGE_REACHED and cond.stage_required:
                req_idx  = self.STAGE_ORDER.index(cond.stage_required) if cond.stage_required in self.STAGE_ORDER else 99
                curr_idx = self.STAGE_ORDER.index(stage) if stage in self.STAGE_ORDER else 0
                if curr_idx < req_idx:
                    return False
            if t == UnlockTrigger.BETA_USERS_MIN and cond.threshold:
                if profile.beta_users_count < cond.threshold:
                    return False
            if t == UnlockTrigger.REVENUE_LIVE and not profile.has_revenue:
                return False
            if t == UnlockTrigger.INVESTOR_INTEREST and not profile.investor_interest:
                return False
            if t == UnlockTrigger.TEAM_SIZE_MIN and cond.threshold:
                if profile.team_size < cond.threshold:
                    return False
        return True


# ============================================================================
# ADAPTIVE TRAINING SERVICE (Integration Layer)
# ============================================================================

class AdaptiveTrainingService:
    """
    Service layer -- replaces the old fixed TrainingCurriculumService.
    Called by AdaptiveTrainingAgent in agent_orchestration.py.
    """

    def __init__(self) -> None:
        self.engine   = AdaptiveCurriculumEngine()
        self.lib_ids  = ModuleLibrary.by_id()

    def generate_curriculum(
        self,
        user_id:                   str,
        role:                      str,
        industry:                  str,
        project_stage:             str,
        hours_available_per_week:  float,
        learning_pace:             str             = "standard",
        target_mvp_weeks:          int             = 0,
        has_technical_skills:      bool            = False,
        team_size:                 int             = 1,
        has_cofounder:             bool            = False,
        pre_existing_skills:       Optional[List[str]] = None,
        unicorn_score:             float           = 0.0,
        beta_users_count:          int             = 0,
        has_revenue:               bool            = False,
        investor_interest:         bool            = False,
    ) -> Dict[str, Any]:
        """Generate a fully adaptive, personalised curriculum. Duration NOT fixed."""
        pace_map = {
            "intensive": LearningPace.INTENSIVE,
            "standard":  LearningPace.STANDARD,
            "part_time": LearningPace.PART_TIME,
        }
        profile = LearnerProfile(
            user_id=user_id, role=role, industry=industry,
            project_stage=project_stage,
            hours_available_per_week=hours_available_per_week,
            learning_pace=pace_map.get(learning_pace, LearningPace.STANDARD),
            target_mvp_weeks=target_mvp_weeks,
            has_technical_skills=has_technical_skills,
            team_size=team_size, has_cofounder=has_cofounder,
            pre_existing_skills=pre_existing_skills or [],
            unicorn_score=unicorn_score, current_stage=project_stage,
            beta_users_count=beta_users_count,
            has_revenue=has_revenue, investor_interest=investor_interest,
        )
        curriculum = self.engine.build(profile)
        time_data  = self.engine.time_engine.estimate(profile)

        return {
            "curriculum_id": curriculum.curriculum_id,
            "user_id":       user_id,
            "learning_summary": {
                "estimated_weeks_to_mvp":      curriculum.estimated_weeks_to_mvp,
                "estimated_total_hours":       curriculum.estimated_hours_to_mvp,
                "weekly_learning_target_hours": time_data["weekly_learning_target_hours"],
                "mvp_target_date":             time_data["mvp_target_date"],
                "learning_pace":               learning_pace,
            },
            "pre_mvp": {
                "total_modules":  len(curriculum.pre_mvp_modules),
                "critical_count": sum(1 for m in curriculum.pre_mvp_modules
                                     if m.priority == ModulePriority.CRITICAL),
                "modules": [self._fmt(m) for m in curriculum.pre_mvp_modules],
            },
            "post_mvp": {
                "tracks_available":       [t.value for t in curriculum.post_mvp_tracks_available],
                "unlocked_modules":       [self._fmt(m) for m in curriculum.post_mvp_modules_unlocked],
                "locked_module_count":    len(curriculum.post_mvp_modules_locked),
                "locked_modules_preview": [
                    {"title": m.title, "track": m.track.value,
                     "unlock_hint": self._hint(m)}
                    for m in curriculum.post_mvp_modules_locked[:5]
                ],
            },
            "next_module":             self._fmt(curriculum.next_module) if curriculum.next_module else None,
            "certifications_eligible": curriculum.certifications_eligible,
            "generated_at":            curriculum.generated_at.isoformat(),
        }

    def _fmt(self, m: TrainingModule) -> Dict:
        return {
            "module_id":      m.module_id,
            "title":          m.title,
            "description":    m.description,
            "objective":      m.learning_objective,
            "zone":           m.zone.value,
            "track":          m.track.value,
            "phase":          m.phase.value,
            "priority":       m.priority.value,
            "estimated_hours": m.estimated_hours,
            "formats":        [f.value for f in m.formats],
            "tags":           m.tags,
            "certification":  m.certification_contribution,
        }

    def _hint(self, m: TrainingModule) -> str:
        for c in m.unlock_conditions:
            if c.trigger == UnlockTrigger.STAGE_REACHED:
                return f"Unlocks at {c.stage_required} stage"
            if c.trigger == UnlockTrigger.BETA_USERS_MIN:
                return f"Unlocks with {int(c.threshold or 0)}+ beta users"
            if c.trigger == UnlockTrigger.REVENUE_LIVE:
                return "Unlocks when revenue is live"
            if c.trigger == UnlockTrigger.INVESTOR_INTEREST:
                return "Unlocks when investor expresses interest"
            if c.trigger == UnlockTrigger.TEAM_SIZE_MIN:
                return f"Unlocks when team reaches {int(c.threshold or 0)} members"
        return "Unlocks based on progress"


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_adaptive_training() -> None:
    svc = AdaptiveTrainingService()

    print("=" * 65)
    print("TECHIT -- ADAPTIVE TRAINING MODULE SYSTEM")
    print("=" * 65)

    # Scenario 1: Solo non-technical founder, idea stage
    print("\n🧑‍🚀 Solo non-technical founder -- idea stage, 8h/week")
    c1 = svc.generate_curriculum(
        user_id="founder_solo", role="founder", industry="healthtech",
        project_stage="idea", hours_available_per_week=8,
        learning_pace="standard", has_technical_skills=False, team_size=1,
    )
    ls = c1["learning_summary"]
    print(f"   Weeks to MVP:    {ls['estimated_weeks_to_mvp']}")
    print(f"   Total hours:     {ls['estimated_total_hours']}")
    print(f"   MVP target:      {ls['mvp_target_date']}")
    print(f"   Pre-MVP modules: {c1['pre_mvp']['total_modules']} "
          f"({c1['pre_mvp']['critical_count']} critical)")
    print(f"   Next module:     {c1['next_module']['title']}")

    # Scenario 2: Technical team, intensive pace
    print("\n🛠  Technical co-founder team -- validation, intensive 20h/week")
    c2 = svc.generate_curriculum(
        user_id="founder_tech", role="hybrid", industry="fintech",
        project_stage="validation", hours_available_per_week=20,
        learning_pace="intensive", target_mvp_weeks=6,
        has_technical_skills=True, team_size=2, has_cofounder=True,
    )
    ls2 = c2["learning_summary"]
    print(f"   Weeks to MVP:    {ls2['estimated_weeks_to_mvp']}")
    print(f"   MVP target:      {ls2['mvp_target_date']}")
    print(f"   Certs eligible:  {c2['certifications_eligible']}")

    # Scenario 3: Post-MVP with revenue + investor interest
    print("\n🚀 Post-MVP -- revenue live, investor interest, 5h/week")
    c3 = svc.generate_curriculum(
        user_id="founder_scale", role="founder", industry="edtech",
        project_stage="growth", hours_available_per_week=5,
        learning_pace="part_time", has_technical_skills=False,
        team_size=4, has_cofounder=True, unicorn_score=79.0,
        beta_users_count=250, has_revenue=True, investor_interest=True,
    )
    print(f"   Pre-MVP modules: {c3['pre_mvp']['total_modules']}")
    print(f"   Post-MVP tracks: {c3['post_mvp']['tracks_available']}")
    print(f"   Unlocked:        {len(c3['post_mvp']['unlocked_modules'])}")
    if c3["post_mvp"]["unlocked_modules"]:
        first = c3["post_mvp"]["unlocked_modules"][0]
        print(f"   First post-MVP:  {first['title']}  ({first['track']})")

    # Library summary
    all_mods = ModuleLibrary.all_modules()
    by_zone  = {}
    by_track = {}
    for m in all_mods:
        by_zone[m.zone.value]   = by_zone.get(m.zone.value, 0)   + 1
        by_track[m.track.value] = by_track.get(m.track.value, 0) + 1
    print(f"\n📚 Module Library: {len(all_mods)} canonical modules")
    for z, n in sorted(by_zone.items()):
        print(f"   {z:10s}: {n}")

    print("=" * 65)


if __name__ == "__main__":
    example_adaptive_training()
