"""
TECHIT DATABASE SCHEMA
======================
Complete PostgreSQL + pgvector schema for the TechIT AI Incubation Platform.

Design Principles
─────────────────
1. Prompts are data -- versioned, A/B-testable, never hardcoded
2. Three-tier memory: Redis (short-term) | PostgreSQL (structured) | Vector DB (semantic)
3. Event-driven -- every significant action is a logged event
4. IP protection built-in -- idea fingerprinting + leak detection
5. Hybrid billing -- subscription + PAYG credit ledger, immutable
6. All scores snapshotted -- trend analysis, investor reports, decay tracking
7. Training is adaptive -- no fixed week numbers, time-to-MVP driven

Table Groups
────────────
  Core Users & Projects
  AI Prompt Registry
  Hybrid Billing & Credits
  AI Execution Log
  Scoring Engine (GSIS, UPS, EVI-I, WCRS, all components)
  Evaluation Engine
  Market Readiness Tracker
  Matching Engine
  Investor Intelligence (EVI-I snapshots, watchlist, alerts)
  Adaptive Training System (no fixed weeks)
  Community & Feed (Hangout)
  Organization Sphere
  Vector Embeddings (skill, idea, feed)
  Agent Execution Log
  Event Log
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    ARRAY, Boolean, Column, DECIMAL, ForeignKey, Index, Integer,
    Float, String, Text, TIMESTAMP,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class RoleEnum(str, Enum):
    FOUNDER         = "founder"
    COLLABORATOR    = "collaborator"
    INVESTOR        = "investor"
    ADMIN           = "admin"
    ACCELERATOR_MGR = "accelerator_manager"


class SubscriptionTierEnum(str, Enum):
    FREE         = "free"
    BUILDER      = "builder"
    FOUNDER_PRO  = "founder_pro"
    INVESTOR     = "investor"
    ENTERPRISE   = "enterprise"


class ProjectStageEnum(str, Enum):
    IDEA       = "idea"
    VALIDATION = "validation"
    MVP        = "mvp"
    BETA       = "beta"
    LAUNCH     = "launch"
    GROWTH     = "growth"
    SCALE      = "scale"


class PromptTypeEnum(str, Enum):
    TRAINING            = "training"
    TOUR_GUIDE          = "tour_guide"
    EVALUATION          = "evaluation"
    RECOMMENDATION      = "recommendation"
    MATCHING            = "matching"
    RISK_ANALYSIS       = "risk_analysis"
    INVESTOR_SIGNAL     = "investor_signal"
    UNICORN_ANALYSIS    = "unicorn_analysis"
    MARKET_INTELLIGENCE = "market_intelligence"
    BUSINESS_PLAN       = "business_plan"
    TECH_ARCHITECTURE   = "tech_architecture"
    EXECUTION_ROADMAP   = "execution_roadmap"
    PIVOT_INTELLIGENCE  = "pivot_intelligence"
    DASHBOARD           = "dashboard"
    FEED                = "feed"
    WORKSPACE           = "workspace"
    ORG_SPHERE          = "org_sphere"
    PROFILE_ANALYSIS    = "profile_analysis"
    ADMIN_MONITOR       = "admin_monitor"
    INVESTOR_EVI        = "investor_evi"
    GSIS                = "gsis"


class AgentTypeEnum(str, Enum):
    VENTURE_INTAKE         = "venture_intake"
    UNICORN_EVALUATOR      = "unicorn_evaluator"
    MARKET_INTELLIGENCE    = "market_intelligence"
    PRODUCT_FEASIBILITY    = "product_feasibility"
    STARTUP_STRATEGY       = "startup_strategy"
    FINANCE_STRATEGY       = "finance_strategy"
    INVESTOR_INTELLIGENCE  = "investor_intelligence"
    BUSINESS_PLAN_GEN      = "business_plan_generator"
    TECH_ARCHITECT         = "tech_architect"
    PIVOT_INTELLIGENCE     = "pivot_intelligence"
    TOUR_GUIDE             = "tour_guide"
    ADAPTIVE_TRAINING      = "adaptive_training"
    MATCHING               = "matching"
    RISK_EVALUATOR         = "risk_evaluator"
    WORKSPACE_ASSISTANT    = "workspace_assistant"
    FEED_INTELLIGENCE      = "feed_intelligence"
    DASHBOARD_INTELLIGENCE = "dashboard_intelligence"
    AI_PROFILE             = "ai_profile"
    ORG_SPHERE             = "org_sphere"
    ADMIN_MONITOR          = "admin_monitor"
    GSIS_COMPUTE           = "gsis_compute"


class BillingEventTypeEnum(str, Enum):
    SUBSCRIPTION_STARTED   = "subscription_started"
    SUBSCRIPTION_RENEWED   = "subscription_renewed"
    SUBSCRIPTION_UPGRADED  = "subscription_upgraded"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    CREDITS_PURCHASED      = "credits_purchased"
    CREDITS_DEDUCTED       = "credits_deducted"
    CREDITS_RESET_MONTHLY  = "credits_reset_monthly"
    CREDITS_REFUNDED       = "credits_refunded"
    PAYWALL_HIT            = "paywall_hit"
    PAYWALL_CONVERTED      = "paywall_converted"
    REFERRAL_CREDIT_EARNED = "referral_credit_earned"


class TrainingZoneEnum(str, Enum):
    PRE_MVP  = "pre_mvp"
    POST_MVP = "post_mvp"


class TrainingTrackEnum(str, Enum):
    FOUNDER     = "founder"
    BUILDER     = "builder"
    INVESTOR    = "investor"
    HYBRID      = "hybrid"
    GROWTH      = "growth"
    REVENUE     = "revenue"
    FUNDRAISING = "fundraising"
    SCALE       = "scale"
    OPERATIONS  = "operations"


class VoiceProviderEnum(str, Enum):
    ELEVENLABS = "elevenlabs"
    PLAYHT     = "playht"
    OPENAI     = "openai"


# ============================================================================
# CORE USERS & PROJECTS
# ============================================================================

class User(Base):
    """
    Core user. Subscription tier controls AI access and credit allocation.
    Both subscription_credits_remaining and payg_credits_balance tracked.
    """
    __tablename__ = "users"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email             = Column(String(255), unique=True, nullable=False)
    full_name         = Column(String(255))
    role              = Column(SQLEnum(RoleEnum), nullable=False)
    subscription_tier = Column(SQLEnum(SubscriptionTierEnum), nullable=False,
                               default=SubscriptionTierEnum.FREE)
    plan_id           = Column(String(50))  # FK to plan registry (billing_system.py)

    # Hybrid credit system (subscription + PAYG running simultaneously)
    subscription_credits_remaining = Column(Integer, default=5, nullable=False)
    subscription_resets_at         = Column(TIMESTAMP)
    payg_credits_balance           = Column(Integer, default=0, nullable=False)
    total_credits_used             = Column(Integer, default=0, nullable=False)

    # Profile signals
    profile_completeness_pct = Column(Float, default=0.0)
    github_connected         = Column(Boolean, default=False)
    linkedin_connected        = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_login = Column(TIMESTAMP)

    projects         = relationship("Project",              back_populates="owner")
    ai_outputs       = relationship("AIOutput",             back_populates="user")
    prompts_created  = relationship("AIPrompt",             back_populates="creator")
    skill_embeddings = relationship("UserSkillEmbedding",   back_populates="user")
    credit_ledger    = relationship("CreditLedger",         back_populates="user")
    score_snapshots  = relationship("ScoreSnapshot",        back_populates="user")
    paywall_hits     = relationship("PaywallHit",           back_populates="user")
    referrals_made   = relationship("ReferralEvent",        back_populates="referrer",
                                    foreign_keys="ReferralEvent.referrer_id")

    __table_args__ = (Index("idx_user_email", "email"), Index("idx_user_role", "role"))


class Project(Base):
    """
    Core startup project. Tracks all scores, stage, and decay.
    """
    __tablename__ = "projects"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title    = Column(String(255), nullable=False)
    tagline  = Column(String(500))
    stage    = Column(SQLEnum(ProjectStageEnum), default=ProjectStageEnum.IDEA)
    industry = Column(String(100))

    # All scores (updated by agents)
    gsis_score              = Column(Float, default=0.0)  # Global Startup Intelligence Score
    unicorn_potential_score = Column(Float, default=0.0)
    market_readiness_score  = Column(Float, default=0.0)
    investment_score        = Column(Float, default=0.0)
    wcrs_score              = Column(Float, default=0.0)   # Marketplace ranking
    evi_score               = Column(Float, default=0.0)   # Execution Velocity (founder)
    evi_i_score             = Column(Float, default=0.0)   # EVI-I (investor view)
    pps_score               = Column(Float, default=0.0)   # Product Progress Score
    cis_score               = Column(Float, default=0.0)   # Community Influence Score
    iis_score               = Column(Float, default=0.0)   # Investor Interest Score

    # Decay tracking
    days_since_update = Column(Integer, default=0)
    last_milestone_at = Column(TIMESTAMP)
    decay_factor      = Column(Float, default=1.0)

    # Compliance & transparency
    compliance_items   = Column(JSON, default={})
    transparency_items = Column(JSON, default={})

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner          = relationship("User",              back_populates="projects")
    ai_outputs     = relationship("AIOutput",           back_populates="project")
    idea_embedding = relationship("IdeaEmbedding",      back_populates="project", uselist=False)
    milestones     = relationship("ProjectMilestone",   back_populates="project")
    evaluations    = relationship("Evaluation",         back_populates="project")
    readiness      = relationship("ReadinessTracker",   back_populates="project", uselist=False)
    wcrs_history   = relationship("WCRSHistory",        back_populates="project")
    score_snapshots = relationship("ScoreSnapshot",     back_populates="project")
    evi_i_snapshots = relationship("InvestorEVISnapshot", back_populates="project")

    __table_args__ = (
        Index("idx_project_owner", "owner_id"),
        Index("idx_project_stage", "stage"),
        Index("idx_project_wcrs",  "wcrs_score"),
        Index("idx_project_gsis",  "gsis_score"),
    )


# ============================================================================
# AI PROMPT REGISTRY
# ============================================================================

class AIPrompt(Base):
    """
    Single source of truth for all TechIT prompts.
    Versioned, role-scoped, A/B-testable. This IS TechIT's intellectual property.
    """
    __tablename__ = "ai_prompts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name         = Column(String(255), nullable=False)
    prompt_type  = Column(SQLEnum(PromptTypeEnum), nullable=False)
    target_role  = Column(SQLEnum(RoleEnum), nullable=False)
    min_tier     = Column(SQLEnum(SubscriptionTierEnum), default=SubscriptionTierEnum.FREE)
    description  = Column(Text)
    system_prompt         = Column(Text, nullable=False)
    user_prompt_template  = Column(Text, nullable=False)
    output_format         = Column(Text)
    credit_cost           = Column(Integer, default=1)
    version    = Column(Integer, default=1, nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    ab_group   = Column(String(10))  # "A" or "B"
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator  = relationship("User",          back_populates="prompts_created")
    outputs  = relationship("AIOutput",      back_populates="prompt")
    metrics  = relationship("PromptMetric",  back_populates="prompt")

    __table_args__ = (
        Index("idx_prompt_type_role", "prompt_type", "target_role", "is_active"),
        Index("idx_prompt_version",   "name", "version"),
    )


# ============================================================================
# HYBRID BILLING & CREDIT SYSTEM
# ============================================================================

class CreditLedger(Base):
    """
    Immutable ledger of every credit transaction.
    Both subscription and PAYG credits logged here.

    Resolution order (enforced by HybridCreditEngine):
      subscription_credits deducted first -> overflow into payg_credits.
    """
    __tablename__ = "credit_ledger"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_type       = Column(SQLEnum(BillingEventTypeEnum), nullable=False)
    credits_delta    = Column(Integer, nullable=False)     # negative = deduction
    credits_after    = Column(Integer, nullable=False)     # total after transaction
    from_subscription = Column(Integer, default=0)         # credits taken from sub allocation
    from_payg        = Column(Integer, default=0)           # credits taken from PAYG balance
    usd_charged_payg = Column(DECIMAL(10, 4), default=0)   # cost for PAYG portion
    task_type        = Column(String(100))
    operation_id     = Column(String(100))
    plan_id          = Column(String(50))
    description      = Column(Text)
    created_at       = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_ledger")

    __table_args__ = (
        Index("idx_credit_user_created", "user_id", "created_at"),
        Index("idx_credit_event_type",   "event_type", "created_at"),
    )


class CreditPurchase(Base):
    """PAYG credit pack purchases -- for billing reconciliation."""
    __tablename__ = "credit_purchases"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    credits_qty = Column(Integer, nullable=False)
    amount_usd  = Column(DECIMAL(10, 2), nullable=False)
    stripe_id   = Column(String(255))
    status      = Column(String(20), default="completed")
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_purchase_user", "user_id"),)


class PaywallHit(Base):
    """
    Every paywall hit logged for conversion analytics and A/B testing.
    converted + converted_at updated when user upgrades after hitting paywall.
    """
    __tablename__ = "paywall_hits"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role           = Column(SQLEnum(RoleEnum))
    plan_id        = Column(String(50))
    operation_id   = Column(String(100))
    paywall_copy   = Column(Text)
    upgrade_cta    = Column(Text)
    upgrade_plan_id = Column(String(50))
    context_vars   = Column(JSON, default={})
    converted      = Column(Boolean, default=False)
    converted_at   = Column(TIMESTAMP)
    hit_at         = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", back_populates="paywall_hits")

    __table_args__ = (
        Index("idx_paywall_user",       "user_id", "hit_at"),
        Index("idx_paywall_operation",  "operation_id", "converted"),
    )


class ReferralEvent(Base):
    """Referral rewards earned through invites and viral locks."""
    __tablename__ = "referral_events"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referred_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action_type    = Column(String(50))   # invite_collaborator / invite_founder / invite_org
    credits_earned = Column(Integer, default=0)
    usd_credit     = Column(DECIMAL(10, 2), default=0)
    credibility_pts = Column(Integer, default=0)
    free_months    = Column(Integer, default=0)
    created_at     = Column(TIMESTAMP, default=datetime.utcnow)

    referrer = relationship("User", back_populates="referrals_made",
                            foreign_keys=[referrer_id])

    __table_args__ = (Index("idx_referral_referrer", "referrer_id"),)


# ============================================================================
# AI EXECUTION LOG
# ============================================================================

class AIOutput(Base):
    """
    Every single AI execution recorded.
    Cost, credits, model, tokens, and user feedback all tracked.
    """
    __tablename__ = "ai_outputs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id  = Column(UUID(as_uuid=True), ForeignKey("ai_prompts.id"), nullable=False)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    input_data       = Column(JSON)
    output_text      = Column(Text, nullable=False)
    confidence_score = Column(DECIMAL(3, 2))
    task_type        = Column(String(100), nullable=False)
    model_used       = Column(String(100), nullable=False)
    tokens_used      = Column(Integer)
    execution_time_ms = Column(Integer)
    cost             = Column(DECIMAL(10, 6))
    credits_consumed = Column(Integer, default=0)
    from_subscription = Column(Integer, default=0)
    from_payg        = Column(Integer, default=0)
    usd_charged_payg = Column(DECIMAL(10, 4), default=0)
    subscription_tier = Column(String(20))
    ip_protected     = Column(Boolean, default=False)
    cached           = Column(Boolean, default=False)
    user_rating      = Column(Integer)
    flagged_for_review = Column(Boolean, default=False)
    created_at       = Column(TIMESTAMP, default=datetime.utcnow)

    user    = relationship("User",    back_populates="ai_outputs")
    project = relationship("Project", back_populates="ai_outputs")
    prompt  = relationship("AIPrompt", back_populates="outputs")
    audio_outputs = relationship("AIAudioOutput", back_populates="ai_output",
                                  cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_output_user_created", "user_id",    "created_at"),
        Index("idx_output_project",      "project_id"),
        Index("idx_output_task_type",    "task_type"),
        Index("idx_output_cost",         "cost"),
    )


class AIAudioOutput(Base):
    """Audio versions of AI outputs (Tour Guide briefings, training narration)."""
    __tablename__ = "ai_audio_outputs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_output_id   = Column(UUID(as_uuid=True), ForeignKey("ai_outputs.id"), nullable=False)
    voice_provider = Column(SQLEnum(VoiceProviderEnum), nullable=False)
    audio_url      = Column(Text, nullable=False)
    duration_seconds = Column(Integer)
    voice_id       = Column(String(100))
    language       = Column(String(10), default="en")
    created_at     = Column(TIMESTAMP, default=datetime.utcnow)

    ai_output = relationship("AIOutput", back_populates="audio_outputs")

    __table_args__ = (Index("idx_audio_output_id", "ai_output_id"),)


# ============================================================================
# UNIFIED SCORING ENGINE TABLES
# ============================================================================

class ScoreSnapshot(Base):
    """
    Point-in-time snapshot of all 15+ scores for a project.
    Enables trend dashboards, investor reports, and decay visualization.
    """
    __tablename__ = "score_snapshots"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))

    # Master score
    gsis_score              = Column(Float)

    # Component scores
    unicorn_potential_score  = Column(Float)
    execution_velocity_index = Column(Float)   # EVI (founder)
    evi_i_adjusted           = Column(Float)   # EVI-I (investor)
    revenue_growth_signal    = Column(Float)
    beta_satisfaction_score  = Column(Float)
    compliance_score         = Column(Float)
    market_readiness_score   = Column(Float)
    transparency_score       = Column(Float)
    founder_reliability_score = Column(Float)
    community_influence_score = Column(Float)  # CIS
    investor_interest_score  = Column(Float)   # IIS
    product_progress_score   = Column(Float)   # PPS
    team_strength_score      = Column(Float)   # TSS
    investment_score         = Column(Float)
    wcrs_adjusted_score      = Column(Float)
    decay_factor             = Column(Float)

    # Context at snapshot time
    days_since_update  = Column(Integer)
    quality_flags      = Column(Integer)
    snapshot_trigger   = Column(String(100))
    alert_score        = Column(Float)
    alert_triggered    = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user    = relationship("User",    back_populates="score_snapshots")
    project = relationship("Project", back_populates="score_snapshots",
                           foreign_keys=[project_id])

    __table_args__ = (
        Index("idx_score_user_created",    "user_id",    "created_at"),
        Index("idx_score_project_created", "project_id", "created_at"),
        Index("idx_score_gsis",            "gsis_score"),
    )


class WCRSHistory(Base):
    """Historical WCRS marketplace ranking for trend charts."""
    __tablename__ = "wcrs_history"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id       = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    base_wcrs        = Column(Float, nullable=False)
    quality_multiplier = Column(Float, nullable=False)
    decay_factor     = Column(Float, nullable=False)
    adjusted_score   = Column(Float, nullable=False)
    quality_flags    = Column(Integer, default=0)
    days_since_update = Column(Integer, default=0)
    created_at       = Column(TIMESTAMP, default=datetime.utcnow)

    project = relationship("Project", back_populates="wcrs_history")

    __table_args__ = (Index("idx_wcrs_project_created", "project_id", "created_at"),)


# ============================================================================
# INVESTOR INTELLIGENCE -- EVI-I SNAPSHOTS
# ============================================================================

class InvestorEVISnapshot(Base):
    """
    EVI-I (Execution Velocity Index for Investor Intelligence) snapshots.
    6-dimensional investor-grade execution signal, decay-adjusted.

    Dimensions:
      MDR  25%  Milestone Delivery Rate
      IS   20%  Iteration Speed
      TRV  15%  Team Response Velocity
      RTA  20%  Revenue Traction Acceleration
      UGM  10%  User Growth Momentum
      CEV  10%  Capital Efficiency Velocity
    """
    __tablename__ = "investor_evi_snapshots"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    mdr_score  = Column(DECIMAL(5, 2))
    is_score   = Column(DECIMAL(5, 2))
    trv_score  = Column(DECIMAL(5, 2))
    rta_score  = Column(DECIMAL(5, 2))
    ugm_score  = Column(DECIMAL(5, 2))
    cev_score  = Column(DECIMAL(5, 2))

    raw_evi_i      = Column(DECIMAL(5, 2), nullable=False)
    decay_factor   = Column(DECIMAL(6, 4), nullable=False)
    adjusted_evi_i = Column(DECIMAL(5, 2), nullable=False)

    signal          = Column(String(30), nullable=False)
    velocity_risk   = Column(String(10), nullable=False)
    trend           = Column(String(20))
    trend_delta     = Column(DECIMAL(6, 2))

    headline    = Column(Text)
    strengths   = Column(JSON)
    red_flags   = Column(JSON)
    watch_items = Column(JSON)

    data_freshness    = Column(String(10), default="current")
    days_since_update = Column(Integer)
    computed_at       = Column(TIMESTAMP, default=datetime.utcnow)

    project = relationship("Project", back_populates="evi_i_snapshots")

    __table_args__ = (
        Index("idx_evi_project_computed", "project_id", "computed_at"),
        Index("idx_evi_adjusted",         "adjusted_evi_i"),
        Index("idx_evi_signal",           "signal", "computed_at"),
    )


class InvestorWatchlist(Base):
    """Investor watchlist with score threshold alerts."""
    __tablename__ = "investor_watchlist"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    alert_threshold_score = Column(Float)
    notes      = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_watchlist_investor", "investor_id"),)


class InvestorAlert(Base):
    """Alerts fired when watchlist thresholds are crossed."""
    __tablename__ = "investor_alerts"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    alert_type  = Column(String(50))
    message     = Column(Text)
    read        = Column(Boolean, default=False)
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_alert_investor_read", "investor_id", "read"),)


# ============================================================================
# EVALUATION ENGINE
# ============================================================================

class Evaluation(Base):
    """Deep AI assessment of startup quality -- multi-stage evaluation."""
    __tablename__ = "evaluations"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status       = Column(String(20), default="pending")

    unicorn_potential_score = Column(Float)
    unicorn_classification  = Column(String(50))
    driver_scores           = Column(JSON)
    venture_viability_report   = Column(JSON)
    product_feasibility_report = Column(JSON)
    market_adoption_report     = Column(JSON)
    emerging_trend_rating    = Column(String(10))
    founder_potential_rating = Column(String(10))
    demand_evidence_rating   = Column(String(10))
    growth_control_rating    = Column(String(10))
    venture_stage            = Column(String(20))
    executive_summary        = Column(Text)
    full_evaluation_text     = Column(Text)
    swot_analysis            = Column(JSON)
    key_risks                = Column(JSON)
    recommendations          = Column(JSON)
    version    = Column(Integer, default=1)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="evaluations")

    __table_args__ = (
        Index("idx_eval_project", "project_id"),
        Index("idx_eval_score",   "unicorn_potential_score"),
    )


# ============================================================================
# MARKET READINESS TRACKER
# ============================================================================

class ReadinessTracker(Base):
    """
    Tracks stage-gate progression: Idea -> Validation -> MVP -> Beta -> Launch -> Growth -> Scale.
    Stage-gate criteria must ALL be met before advancing.
    """
    __tablename__ = "readiness_tracker"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id    = Column(UUID(as_uuid=True), ForeignKey("projects.id"),
                           nullable=False, unique=True)
    current_stage = Column(SQLEnum(ProjectStageEnum), default=ProjectStageEnum.IDEA)
    stage_pct     = Column(Float, default=0.0)
    requirements_remaining = Column(JSON, default=[])
    estimated_days_to_next = Column(Integer)
    risk_level    = Column(String(10), default="low")

    idea_criteria_met       = Column(Boolean, default=False)
    validation_criteria_met = Column(Boolean, default=False)
    mvp_criteria_met        = Column(Boolean, default=False)
    beta_criteria_met       = Column(Boolean, default=False)
    launch_criteria_met     = Column(Boolean, default=False)
    growth_criteria_met     = Column(Boolean, default=False)

    last_ai_check = Column(TIMESTAMP)
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at    = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    project    = relationship("Project",          back_populates="readiness")
    milestones = relationship("ReadinessMilestone", back_populates="tracker")

    __table_args__ = (Index("idx_readiness_project", "project_id"),)


class ReadinessMilestone(Base):
    """Individual milestone within a readiness stage gate."""
    __tablename__ = "readiness_milestones"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracker_id   = Column(UUID(as_uuid=True), ForeignKey("readiness_tracker.id"), nullable=False)
    stage        = Column(SQLEnum(ProjectStageEnum), nullable=False)
    title        = Column(String(255), nullable=False)
    description  = Column(Text)
    is_required  = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(TIMESTAMP)
    evidence     = Column(Text)
    ai_inferred  = Column(Boolean, default=False)

    tracker = relationship("ReadinessTracker", back_populates="milestones")

    __table_args__ = (Index("idx_milestone_tracker_stage", "tracker_id", "stage"),)


class ProjectMilestone(Base):
    """General workspace-level project milestone."""
    __tablename__ = "project_milestones"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    title        = Column(String(255), nullable=False)
    description  = Column(Text)
    due_date     = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    is_completed = Column(Boolean, default=False)
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)

    project = relationship("Project", back_populates="milestones")
    __table_args__ = (Index("idx_milestone_project", "project_id"),)


# ============================================================================
# ADAPTIVE TRAINING SYSTEM (NO FIXED WEEKS)
# ============================================================================

class LearnerProfile(Base):
    """
    Computed learning profile per user. Drives adaptive curriculum generation.
    Duration is derived from time-to-MVP, NOT a fixed week number.
    """
    __tablename__ = "learner_profiles"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                  = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    role                     = Column(String(20))
    industry                 = Column(String(100))
    project_stage            = Column(String(20))
    hours_available_per_week = Column(Float, default=8.0)
    learning_pace            = Column(String(20), default="standard")  # intensive/standard/part_time
    target_mvp_weeks         = Column(Integer, default=0)              # 0 = engine estimates
    estimated_weeks_to_mvp   = Column(Float)                           # Engine output
    has_technical_skills     = Column(Boolean, default=False)
    has_cofounder            = Column(Boolean, default=False)
    pre_existing_skills      = Column(JSON, default=[])
    unicorn_score            = Column(Float, default=0.0)
    beta_users_count         = Column(Integer, default=0)
    has_revenue              = Column(Boolean, default=False)
    investor_interest        = Column(Boolean, default=False)
    created_at               = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at               = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    curriculum   = relationship("PersonalisedCurriculum", back_populates="learner", uselist=False)
    __table_args__ = (Index("idx_learner_user", "user_id"),)


class PersonalisedCurriculum(Base):
    """
    Generated adaptive curriculum per user.
    Linked to learner_profile. No fixed week count -- duration is computed.
    Post-MVP tracks stored as JSON, unlocked conditionally.
    """
    __tablename__ = "personalised_curricula"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    learner_id      = Column(UUID(as_uuid=True), ForeignKey("learner_profiles.id"))

    # Pre-MVP
    pre_mvp_module_ids        = Column(JSON, default=[])  # ordered list of module_ids
    estimated_weeks_to_mvp    = Column(Float)
    estimated_hours_to_mvp    = Column(Float)
    weekly_learning_target_hrs = Column(Float)
    mvp_target_date           = Column(String(20))

    # Post-MVP
    post_mvp_tracks_available  = Column(JSON, default=[])
    post_mvp_unlocked_ids      = Column(JSON, default=[])
    post_mvp_locked_ids        = Column(JSON, default=[])

    # Progress
    completed_module_ids    = Column(JSON, default=[])
    in_progress_module_ids  = Column(JSON, default=[])
    next_module_id          = Column(String(20))

    # Certifications
    certifications_earned    = Column(JSON, default=[])
    certifications_eligible  = Column(JSON, default=[])

    # Adaptation history
    adaptation_count   = Column(Integer, default=0)
    last_adapted_at    = Column(TIMESTAMP)
    adaptation_reason  = Column(Text)

    generated_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at   = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    learner   = relationship("LearnerProfile", back_populates="curriculum")
    progress  = relationship("ModuleProgress",  back_populates="curriculum")

    __table_args__ = (Index("idx_curriculum_user", "user_id"),)


class ModuleProgress(Base):
    """
    Per-module completion record.
    Stores quiz scores, AI review results, and exercise submissions.
    """
    __tablename__ = "module_progress"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_id = Column(UUID(as_uuid=True), ForeignKey("personalised_curricula.id"), nullable=False)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"),                  nullable=False)
    module_id     = Column(String(20), nullable=False)    # e.g. "fv_001"
    module_title  = Column(String(255))
    zone          = Column(SQLEnum(TrainingZoneEnum))
    track         = Column(SQLEnum(TrainingTrackEnum))

    status        = Column(String(20), default="locked")  # locked/unlocked/in_progress/complete
    quiz_score    = Column(Float)
    exercise_submitted = Column(Boolean, default=False)
    exercise_url  = Column(Text)
    ai_review_result = Column(Text)
    ai_review_score  = Column(Float)
    self_reported = Column(Boolean, default=False)

    started_at    = Column(TIMESTAMP)
    completed_at  = Column(TIMESTAMP)
    hours_spent   = Column(Float, default=0.0)
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)

    curriculum = relationship("PersonalisedCurriculum", back_populates="progress")

    __table_args__ = (
        Index("idx_progress_curriculum_module", "curriculum_id", "module_id"),
        Index("idx_progress_user_status",       "user_id", "status"),
    )


# ============================================================================
# MATCHING ENGINE
# ============================================================================

class Match(Base):
    """Match results between users. Scored by ScoringEngine.compute_match_score()."""
    __tablename__ = "matches"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seeker_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    match_type   = Column(String(30), nullable=False)

    skill_similarity           = Column(Float)
    goal_similarity            = Column(Float)
    execution_style_similarity = Column(Float)
    availability_overlap       = Column(Float)
    trust_score                = Column(Float)
    domain_experience          = Column(Float)
    match_score                = Column(Float, nullable=False)

    compatibility_explanation = Column(Text)
    risk_flags                = Column(JSON)
    status     = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_match_seeker",    "seeker_id",   "status"),
        Index("idx_match_score",     "match_score"),
    )


# ============================================================================
# COMMUNITY / FEED / HANGOUT
# ============================================================================

class FeedPost(Base):
    """
    Community feed post.
    ai_relevance_score set by FeedIntelligenceAgent at post creation.
    CIS (Community Influence Score) aggregated from post engagement.
    """
    __tablename__ = "feed_posts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    post_type  = Column(String(30))   # milestone/insight/question/achievement/update
    content    = Column(Text, nullable=False)
    tags       = Column(ARRAY(String))
    ai_relevance_score = Column(Float, default=0.0)
    likes_count        = Column(Integer, default=0)
    comments_count     = Column(Integer, default=0)
    trust_weight       = Column(Float, default=1.0)  # VerifiedActivity/TotalActivity anti-spam
    is_pinned          = Column(Boolean, default=False)
    created_at         = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_feed_author",    "author_id",         "created_at"),
        Index("idx_feed_relevance", "ai_relevance_score"),
    )


# ============================================================================
# ORGANIZATION SPHERE
# ============================================================================

class Organization(Base):
    """
    Organization entity. OrgSphereAgent computes ai_health_score.
    TSS (Team Strength Score) stored here.
    """
    __tablename__ = "organizations"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(255), nullable=False)
    owner_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    industry      = Column(String(100))
    org_type      = Column(String(50))
    member_count  = Column(Integer, default=1)
    ai_health_score = Column(Float)
    tss_score     = Column(Float)   # Team Strength Score
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_org_owner", "owner_id"),)


class OrgMember(Base):
    """Organisation membership with role efficiency tracking."""
    __tablename__ = "org_members"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id          = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"),         nullable=False)
    org_role        = Column(String(50))
    role_efficiency = Column(Float)  # Output / AssignedTasks
    joined_at       = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_orgmember_org", "org_id"),)


# ============================================================================
# VECTOR EMBEDDING TABLES
# ============================================================================

class UserSkillEmbedding(Base):
    """Vector embedding of user skills + goals for semantic matching."""
    __tablename__ = "user_skill_embeddings"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    embedding       = Column(Vector(1536))  # 1536 dims (OpenAI) / 1024 (Cohere)
    skill_text      = Column(Text)
    embedding_model = Column(String(100))
    created_at      = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at      = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="skill_embeddings")
    __table_args__ = (Index("idx_user_embedding", "user_id"),)


class IdeaEmbedding(Base):
    """
    Vector embedding of startup idea for IP protection.
    Leak detection: new ideas compared against all existing fingerprints.
    Similarity > 0.95 -> IP alert triggered.
    """
    __tablename__ = "idea_embeddings"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id       = Column(UUID(as_uuid=True), ForeignKey("projects.id"),
                              nullable=False, unique=True)
    embedding        = Column(Vector(1536))
    idea_fingerprint = Column(String(64), unique=True)
    idea_text        = Column(Text)
    embedding_model  = Column(String(100))
    is_protected             = Column(Boolean, default=True)
    leak_detection_enabled   = Column(Boolean, default=True)
    leak_detection_threshold = Column(Float, default=0.95)
    created_at       = Column(TIMESTAMP, default=datetime.utcnow)

    project = relationship("Project", back_populates="idea_embedding")
    __table_args__ = (
        Index("idx_idea_project",     "project_id"),
        Index("idx_idea_fingerprint", "idea_fingerprint"),
    )


# ============================================================================
# PROMPT METRICS
# ============================================================================

class PromptMetric(Base):
    """A/B test results and performance metrics per prompt version."""
    __tablename__ = "prompt_metrics"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id    = Column(UUID(as_uuid=True), ForeignKey("ai_prompts.id"), nullable=False)
    total_execs  = Column(Integer, default=0)
    success_rate = Column(DECIMAL(5, 2))
    avg_rating   = Column(DECIMAL(3, 2))
    avg_time_ms  = Column(Integer)
    avg_tokens   = Column(Integer)
    avg_cost     = Column(DECIMAL(10, 6))
    period       = Column(String(20))
    measured_at  = Column(TIMESTAMP, default=datetime.utcnow)

    prompt = relationship("AIPrompt", back_populates="metrics")
    __table_args__ = (Index("idx_metrics_prompt_period", "prompt_id", "period"),)


# ============================================================================
# AGENT EXECUTION LOG
# ============================================================================

class AgentExecutionLog(Base):
    """Every agent run logged. Enables success rate tracking, cost per agent, alerts."""
    __tablename__ = "agent_execution_logs"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_type   = Column(SQLEnum(AgentTypeEnum), nullable=False)
    agent_version = Column(String(20))
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    trigger_type = Column(String(30))
    trigger_event = Column(JSON)
    success      = Column(Boolean, nullable=False)
    output       = Column(JSON)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    models_called = Column(ARRAY(String))
    total_tokens  = Column(Integer)
    total_cost    = Column(DECIMAL(10, 6))
    credits_consumed = Column(Integer, default=0)
    started_at    = Column(TIMESTAMP, nullable=False)
    completed_at  = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_agent_user_started", "user_id",    "started_at"),
        Index("idx_agent_type_started", "agent_type", "started_at"),
        Index("idx_agent_success",      "agent_type", "success"),
    )


# ============================================================================
# EVENT LOG
# ============================================================================

class EventLog(Base):
    """
    All platform events. Drives the agent orchestration routing.

    Events and their agent triggers (from agent_orchestration.py):
      idea_submitted               -> VentureIntake + RiskEvaluator + Matching
      user_login                   -> TourGuide + Dashboard + GSISCompute
      training_completed           -> AdaptiveTraining
      milestone_updated            -> Dashboard + TourGuide + GSISCompute
      investor_views               -> InvestorIntelligence
      mvp_shipped                  -> AdaptiveTraining + Dashboard
      revenue_went_live            -> AdaptiveTraining + InvestorIntelligence
      pivot_detected               -> PivotIntelligence + AdaptiveTraining
      investor_expressed_interest  -> AdaptiveTraining + InvestorIntelligence
    """
    __tablename__ = "event_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type  = Column(String(100), nullable=False)
    event_data  = Column(JSON)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    processed   = Column(Boolean, default=False)
    processed_at       = Column(TIMESTAMP)
    agents_triggered   = Column(ARRAY(String))
    processing_error   = Column(Text)
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_event_type_created", "event_type", "created_at"),
        Index("idx_event_processed",    "processed",  "created_at"),
        Index("idx_event_user",         "user_id",    "created_at"),
    )



# ============================================================================
# IDEA & SOLUTION HUB TABLES  (8 tables)
# ============================================================================

class ProblemNode(Base):
    """
    A structured real-world problem on the Global Problems Board.

    Problem-Driven pathway entry point (B pathway).
    Can be user-submitted or AI-discovered.
    """
    __tablename__ = "problem_nodes"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title               = Column(String(255), nullable=False)
    description         = Column(Text, nullable=False)
    location            = Column(String(100), default="Global")
    category            = Column(String(50), nullable=False)       # ProblemCategory enum value
    urgency             = Column(String(30), nullable=False)        # ProblemUrgency enum value
    source              = Column(String(50), default="user_submitted")
    who_is_affected     = Column(Text)
    current_solutions   = Column(ARRAY(Text))                      # existing but failed
    sdg_alignment       = Column(ARRAY(String))                    # UN Sustainable Development Goals
    tags                = Column(ARRAY(String))
    impact_score        = Column(DECIMAL(5, 2), default=0.0)
    priority_score      = Column(DECIMAL(5, 2), default=0.0)
    engagement_count    = Column(Integer, default=0)
    ai_summary          = Column(Text)
    stakeholder_map     = Column(JSON)
    related_problem_ids = Column(ARRAY(UUID(as_uuid=True)))
    is_ai_discovered    = Column(Boolean, default=False)
    verified            = Column(Boolean, default=False)
    submitted_by        = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at          = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at          = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_problem_category_urgency", "category", "urgency"),
        Index("idx_problem_impact_score",     "impact_score"),
        Index("idx_problem_priority_score",   "priority_score"),
        Index("idx_problem_submitted_by",     "submitted_by"),
    )


class SolutionProject(Base):
    """
    A solution project converted from a problem discussion.

    Supports ALL solution types -- not just startups:
    startup_for_profit, social_initiative, public_policy,
    community_project, research_project, infrastructure, service_based, hybrid.
    """
    __tablename__ = "solution_projects"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id          = Column(UUID(as_uuid=True), ForeignKey("problem_nodes.id"), nullable=False)
    title               = Column(String(255), nullable=False)
    description         = Column(Text)
    solution_type       = Column(String(50), nullable=False)       # SolutionType enum
    funding_type        = Column(String(50), nullable=False)       # FundingType enum
    stage               = Column(String(30), default="discussion") # SolutionStage enum
    impact_model        = Column(Text)
    execution_plan      = Column(Text)
    required_roles      = Column(ARRAY(String))
    required_resources  = Column(ARRAY(String))
    estimated_cost_usd  = Column(DECIMAL(14, 2))
    estimated_timeline_weeks = Column(Integer)
    impact_score        = Column(DECIMAL(5, 2), default=0.0)
    feasibility_score   = Column(DECIMAL(5, 2), default=0.0)
    sustainability_score = Column(DECIMAL(5, 2), default=0.0)
    readiness_score     = Column(DECIMAL(5, 2), default=0.0)
    contributors        = Column(JSON)
    created_by          = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at          = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at          = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_solution_problem",       "problem_id"),
        Index("idx_solution_type_stage",    "solution_type", "stage"),
        Index("idx_solution_impact_score",  "impact_score"),
        Index("idx_solution_created_by",    "created_by"),
    )


class DiscussionThread(Base):
    """
    A structured discussion thread attached to a ProblemNode.

    Each thread has AI-generated summaries, idea clusters,
    and a strongest-direction signal.
    """
    __tablename__ = "discussion_threads"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id      = Column(UUID(as_uuid=True), ForeignKey("problem_nodes.id"), nullable=False)
    title           = Column(String(255))
    ai_summary      = Column(Text)                         # regularly updated by DiscussionModeratorAgent
    idea_clusters   = Column(JSON)                         # {cluster_label: [contribution_ids]}
    strongest_direction = Column(Text)
    readiness_confidence = Column(DECIMAL(5, 2), default=0.0)
    is_ready_to_convert  = Column(Boolean, default=False)
    contribution_count   = Column(Integer, default=0)
    created_at      = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at      = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_thread_problem",   "problem_id"),
        Index("idx_thread_ready",     "is_ready_to_convert"),
    )


class DiscussionContribution(Base):
    """
    A single typed contribution to a problem discussion thread.

    Unlike Reddit, each contribution is classified:
    idea / insight / resource / critique / data_evidence.
    AI quality score drives ranking and cluster assignment.
    """
    __tablename__ = "discussion_contributions"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id           = Column(UUID(as_uuid=True), ForeignKey("discussion_threads.id"), nullable=False)
    problem_id          = Column(UUID(as_uuid=True), ForeignKey("problem_nodes.id"), nullable=False)
    author_id           = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    contribution_type   = Column(String(30), nullable=False)       # ContributionType enum
    content             = Column(Text, nullable=False)
    ai_quality_score    = Column(DECIMAL(5, 2), default=0.0)       # 0–100, AI-assessed
    cluster_label       = Column(String(100))                      # AI-assigned cluster
    upvotes             = Column(Integer, default=0)
    is_ai_summarised    = Column(Boolean, default=False)
    created_at          = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_contribution_thread",   "thread_id", "created_at"),
        Index("idx_contribution_type",     "contribution_type"),
        Index("idx_contribution_author",   "author_id"),
        Index("idx_contribution_quality",  "ai_quality_score"),
    )


class SolutionDeployment(Base):
    """
    A real-world deployment of a validated solution.

    TechIT deploys solutions -- not just builds them.
    Deployment modes: pilot, NGO rollout, government, startup launch, CSR, community.
    Full checklist tracking with partner onboarding and field feedback linkage.
    """
    __tablename__ = "solution_deployments"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id             = Column(UUID(as_uuid=True), ForeignKey("solution_projects.id"), nullable=False)
    deployment_mode         = Column(String(50), nullable=False)   # DeploymentMode enum
    status                  = Column(String(30), default="pending") # DeploymentStatus enum
    region                  = Column(String(100))
    partner_orgs            = Column(ARRAY(String))
    resources_allocated     = Column(JSON)
    beneficiaries_target    = Column(Integer, default=0)
    beneficiaries_reached   = Column(Integer, default=0)
    deployment_checklist    = Column(JSON)                         # [{item, completed}]
    ai_deployment_plan      = Column(Text)
    readiness_score         = Column(DECIMAL(5, 2), default=0.0)
    notes                   = Column(Text)
    start_date              = Column(TIMESTAMP)
    target_end_date         = Column(TIMESTAMP)
    completed_at            = Column(TIMESTAMP)
    created_by              = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at              = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at              = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_deployment_solution",  "solution_id"),
        Index("idx_deployment_status",    "status"),
        Index("idx_deployment_region",    "region"),
    )


class FieldFeedback(Base):
    """
    Real-world feedback from deployed solutions.

    Closes the Problem -> Solution -> Deployment -> Feedback -> Optimisation loop.
    AI analyses each submission to extract improvements and update impact scores.
    """
    __tablename__ = "field_feedback"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id       = Column(UUID(as_uuid=True), ForeignKey("solution_deployments.id"), nullable=False)
    solution_id         = Column(UUID(as_uuid=True), ForeignKey("solution_projects.id"), nullable=False)
    submitted_by        = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    field_report        = Column(Text)
    beneficiary_feedback = Column(Text)
    impact_metrics      = Column(JSON)                             # actual measured outcomes
    failure_points      = Column(ARRAY(String))
    what_worked         = Column(ARRAY(String))
    usage_data          = Column(JSON)
    ai_analysis         = Column(Text)                             # FieldFeedbackAgent output
    created_at          = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_feedback_deployment",  "deployment_id"),
        Index("idx_feedback_solution",    "solution_id"),
        Index("idx_feedback_submitted",   "submitted_by", "created_at"),
    )


class ImpactSnapshot(Base):
    """
    Periodic snapshot of a solution's real-world impact metrics.
    Enables longitudinal impact tracking over deployment lifetime.
    """
    __tablename__ = "impact_snapshots"

    id                          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id                 = Column(UUID(as_uuid=True), ForeignKey("solution_projects.id"), nullable=False)
    deployment_id               = Column(UUID(as_uuid=True), ForeignKey("solution_deployments.id"))
    impact_score                = Column(DECIMAL(5, 2))
    people_affected_estimate    = Column(DECIMAL(12, 2))
    severity_score              = Column(DECIMAL(4, 2))
    scalability_score           = Column(DECIMAL(4, 2))
    sustainability_score        = Column(DECIMAL(4, 2))
    measurability_score         = Column(DECIMAL(4, 2))
    priority_score              = Column(DECIMAL(5, 2))
    priority_colour             = Column(String(10))               # 🔴🟠🟡🔵
    beneficiaries_reached       = Column(Integer, default=0)
    funds_deployed_usd          = Column(DECIMAL(14, 2))
    snapshot_notes              = Column(Text)
    computed_at                 = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_impact_snapshot_solution",  "solution_id", "computed_at"),
        Index("idx_impact_snapshot_score",     "impact_score"),
    )


class GrantApplication(Base):
    """
    AI-generated grant applications for non-profit and social solutions.
    Linked to a SolutionProject and tracked through submission lifecycle.
    """
    __tablename__ = "grant_applications"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id             = Column(UUID(as_uuid=True), ForeignKey("solution_projects.id"), nullable=False)
    created_by              = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    funder_name             = Column(String(255), nullable=False)
    funding_type            = Column(String(50), nullable=False)   # FundingType enum
    amount_requested_usd    = Column(DECIMAL(14, 2), nullable=False)
    application_text        = Column(Text, nullable=False)         # AI-generated application body
    status                  = Column(String(30), default="draft")  # draft/submitted/approved/rejected
    submitted_at            = Column(TIMESTAMP)
    decision_at             = Column(TIMESTAMP)
    decision_notes          = Column(Text)
    created_at              = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at              = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_grant_solution",   "solution_id"),
        Index("idx_grant_status",     "status"),
        Index("idx_grant_created_by", "created_by"),
    )


# ============================================================================
# DOCUMENT GENERATION TABLES  (3 tables)
# ============================================================================

class GeneratedDocument(Base):
    """
    Stores every AI-generated document.

    8 document types: executive_summary, business_plan, pitch_deck,
    investor_report, unicorn_analysis_report, product_roadmap,
    financial_projection, market_research_report.

    Supports 3 styles × 3 audiences × 4 export formats.
    """
    __tablename__ = "generated_documents"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id      = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_type   = Column(String(50), nullable=False)           # DocumentType enum
    style           = Column(String(20), default="standard")       # concise/standard/detailed
    audience        = Column(String(30), default="investors")      # DocumentAudience enum
    title           = Column(String(500))
    content         = Column(Text, nullable=False)                 # full AI-generated text
    structured_output = Column(JSON)                               # parsed sections dict
    word_count      = Column(Integer, default=0)
    page_estimate   = Column(Integer, default=0)
    investor_mode   = Column(Boolean, default=False)
    model_used      = Column(String(100))
    credits_consumed = Column(Integer, default=0)
    shareable_link  = Column(Text)
    export_urls     = Column(JSON)                                 # {format: url}
    version         = Column(Integer, default=1)
    parent_document_id = Column(UUID(as_uuid=True), ForeignKey("generated_documents.id"), nullable=True)
    generated_at    = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_doc_project_type",   "project_id", "document_type"),
        Index("idx_doc_user",           "user_id",    "generated_at"),
        Index("idx_doc_type_audience",  "document_type", "audience"),
    )


class DocumentExport(Base):
    """
    Tracks every export action for a generated document.
    Supports PDF, Notion Doc, Google Doc, Slide Deck, shareable links.
    """
    __tablename__ = "document_exports"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id     = Column(UUID(as_uuid=True), ForeignKey("generated_documents.id"), nullable=False)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    export_format   = Column(String(30), nullable=False)           # ExportFormat enum
    export_url      = Column(Text)                                 # S3/CDN URL or external doc URL
    file_size_kb    = Column(DECIMAL(10, 2))
    page_count      = Column(Integer)
    is_shareable    = Column(Boolean, default=False)
    share_token     = Column(String(128))                          # for public share links
    expires_at      = Column(TIMESTAMP)
    downloaded_at   = Column(TIMESTAMP)
    created_at      = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_export_document",   "document_id"),
        Index("idx_export_user",       "user_id", "created_at"),
        Index("idx_export_format",     "export_format"),
        Index("idx_export_token",      "share_token"),
    )


class DocumentTemplate(Base):
    """
    Versioned document templates stored as data assets.
    Each DocumentType × DocumentAudience × DocumentStyle combination
    has a registered template that can be A/B tested and improved.
    """
    __tablename__ = "document_templates"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type   = Column(String(50), nullable=False)
    audience        = Column(String(30), nullable=False)
    style           = Column(String(20), nullable=False)
    name            = Column(String(255))
    system_prompt   = Column(Text, nullable=False)
    section_schema  = Column(ARRAY(String))                        # ordered section names
    estimated_pages = Column(Integer)
    version         = Column(Integer, default=1)
    is_active       = Column(Boolean, default=True)
    avg_user_rating = Column(DECIMAL(3, 2))
    total_uses      = Column(Integer, default=0)
    created_by      = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at      = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at      = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_template_type_audience_style", "document_type", "audience", "style"),
        Index("idx_template_active",              "is_active"),
    )



# ============================================================================
# APP SCAFFOLD TABLE  (Prompt -> Live App)
# ============================================================================

class AppScaffold(Base):
    """
    Stores every generated application scaffold.

    One scaffold per project. Re-running scaffold generation creates a new
    version (version field). The latest active scaffold is always the
    canonical one.

    Scaffold types supported:
      nextjs_supabase   -- Next.js 14 + Supabase + Tailwind (default 80%)
      nextjs_prisma     -- Next.js 14 + PostgreSQL + Prisma
      react_firebase    -- React 18 + Firebase
      expo_supabase     -- Expo (React Native) + Supabase
      fastapi_supabase  -- FastAPI + Supabase (API-only)

    Deploy status lifecycle:
      pending -> deploying -> deployed -> failed

    IP protection:
      ip_protected=True on all scaffold AIRequests.
      Scaffold embeds proprietary business logic from the venture profile.
      Row-level security via project_owner RLS policy (inherits from projects).
    """
    __tablename__ = "app_scaffolds"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id      = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Stack selection
    scaffold_type   = Column(String(50), nullable=False, default="nextjs_supabase")
    stack_description = Column(String(255))

    # Generated scaffold content
    pages           = Column(JSON)          # [{route, component_name, description, auth_required}]
    schema_sql      = Column(Text)          # Supabase/Postgres CREATE TABLE statements
    api_routes      = Column(JSON)          # [{method, path, description, auth_required, ...}]
    env_template    = Column(Text)          # .env.example content
    components      = Column(JSON)          # [{name, purpose, props}]
    setup_steps     = Column(JSON)          # ["npm install", "npm run dev", ...]
    deploy_config   = Column(JSON)          # {vercel_json, github_actions_yml, deploy_steps}

    # Deployment tracking
    deploy_status       = Column(String(30), default="pending")  # pending/deploying/deployed/failed
    github_repo_url     = Column(Text)          # GitHub repo URL (post-push)
    vercel_url          = Column(Text)          # Live Vercel URL (post-deploy)
    live_preview_url    = Column(Text)          # techit.app subdomain
    download_url        = Column(Text)          # ZIP download URL
    vercel_deploy_url   = Column(Text)          # 1-click Vercel deploy button URL

    # Metadata
    estimated_build_hours = Column(Integer, default=4)
    ip_protected        = Column(Boolean, default=True)
    version             = Column(Integer, default=1)
    credits_consumed    = Column(Integer, default=0)
    model_used          = Column(String(100))
    generated_at        = Column(TIMESTAMP, default=datetime.utcnow)
    deployed_at         = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("idx_scaffold_project",     "project_id"),
        Index("idx_scaffold_user",        "user_id", "generated_at"),
        Index("idx_scaffold_type_status", "scaffold_type", "deploy_status"),
    )


# ============================================================================
# REFERENCE SQL -- KEY QUERIES
# ============================================================================

REFERENCE_QUERIES = {

    "marketplace_ranking": """
        -- Top startups by GSIS + WCRS adjusted score
        SELECT p.id, p.title, p.industry, p.stage,
               p.gsis_score, p.wcrs_score, p.decay_factor,
               p.unicorn_potential_score, p.investment_score,
               p.evi_i_score
        FROM projects p
        WHERE p.wcrs_score > 0
        ORDER BY p.gsis_score DESC, p.wcrs_score DESC
        LIMIT :limit;
    """,

    "monthly_credit_burn": """
        SELECT u.id, u.subscription_tier,
               u.subscription_credits_remaining,
               u.payg_credits_balance,
               SUM(ABS(cl.credits_delta)) FILTER (WHERE cl.event_type = 'credits_deducted')
                   AS credits_burned,
               SUM(cl.usd_charged_payg) AS payg_usd_spent
        FROM users u
        LEFT JOIN credit_ledger cl ON cl.user_id = u.id
            AND cl.created_at >= date_trunc('month', NOW())
        GROUP BY u.id, u.subscription_tier,
                 u.subscription_credits_remaining, u.payg_credits_balance;
    """,

    "paywall_conversion_rates": """
        SELECT operation_id,
               COUNT(*) AS hits,
               SUM(CASE WHEN converted THEN 1 ELSE 0 END) AS conversions,
               ROUND(SUM(CASE WHEN converted THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1)
                   AS conversion_pct
        FROM paywall_hits
        WHERE hit_at >= NOW() - INTERVAL '30 days'
        GROUP BY operation_id
        ORDER BY conversion_pct DESC;
    """,

    "idea_similarity_check": """
        -- Semantic similarity for IP leak detection (pgvector)
        SELECT ie.project_id, p.title,
               1 - (ie.embedding <=> :query_embedding::vector) AS similarity
        FROM idea_embeddings ie
        JOIN projects p ON ie.project_id = p.id
        WHERE ie.leak_detection_enabled = true
          AND 1 - (ie.embedding <=> :query_embedding::vector) >= ie.leak_detection_threshold
        ORDER BY ie.embedding <=> :query_embedding::vector
        LIMIT 10;
    """,

    "stagnation_roster": """
        -- Projects with decay_factor < 0.70 (≥18 days inactive)
        SELECT p.id, p.title, p.owner_id, p.days_since_update,
               p.decay_factor,
               ROUND((1 - p.decay_factor) * 100, 1) AS score_penalty_pct,
               p.wcrs_score, p.gsis_score
        FROM projects p
        WHERE p.decay_factor < 0.70
          AND p.stage NOT IN ('scale')
        ORDER BY p.decay_factor ASC;
    """,

    "adaptive_training_progress": """
        SELECT u.id, u.full_name, lp.learning_pace,
               lp.estimated_weeks_to_mvp,
               pc.estimated_hours_to_mvp,
               jsonb_array_length(pc.completed_module_ids::jsonb) AS modules_done,
               jsonb_array_length(pc.pre_mvp_module_ids::jsonb) AS modules_total,
               pc.next_module_id,
               pc.adaptation_count, pc.last_adapted_at
        FROM users u
        JOIN learner_profiles lp  ON lp.user_id  = u.id
        JOIN personalised_curricula pc ON pc.user_id = u.id
        WHERE u.role = 'founder';
    """,

    "evi_i_top_performers": """
        -- Top startups by investor EVI-I (latest snapshot)
        SELECT DISTINCT ON (e.project_id)
               e.project_id, p.title, p.industry,
               e.adjusted_evi_i, e.signal, e.velocity_risk,
               e.trend, e.trend_delta, e.headline
        FROM investor_evi_snapshots e
        JOIN projects p ON p.id = e.project_id
        ORDER BY e.project_id, e.computed_at DESC, e.adjusted_evi_i DESC;
    """,

    "agent_performance_7d": """
        SELECT agent_type,
               COUNT(*) AS runs,
               AVG(execution_time_ms) AS avg_ms,
               ROUND(SUM(CASE WHEN success THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1)
                   AS success_pct,
               SUM(credits_consumed) AS total_credits,
               SUM(total_cost) AS total_cost_usd
        FROM agent_execution_logs
        WHERE started_at >= NOW() - INTERVAL '7 days'
        GROUP BY agent_type
        ORDER BY success_pct DESC;
    """,

    "global_impact_dashboard": """
        -- Live global impact metrics for the Idea & Solution Hub dashboard
        SELECT
            COUNT(DISTINCT sp.id)   AS active_solutions,
            COUNT(DISTINCT sd.id)   AS active_deployments,
            SUM(sd.beneficiaries_reached) AS total_people_impacted,
            COUNT(DISTINCT pn.id)   AS active_problems,
            COUNT(DISTINCT sd.region) AS countries_involved,
            SUM(ga.amount_requested_usd)
                FILTER (WHERE ga.status = 'approved') AS funds_deployed_usd
        FROM solution_projects sp
        LEFT JOIN solution_deployments sd ON sd.solution_id = sp.id
            AND sd.status IN ('active', 'scaling', 'completed')
        LEFT JOIN problem_nodes pn ON pn.id = sp.problem_id
        LEFT JOIN grant_applications ga ON ga.solution_id = sp.id;
    """,

    "top_priority_problems": """
        -- Global Problems Board -- ranked by priority score
        SELECT pn.id, pn.title, pn.category, pn.urgency,
               pn.location, pn.impact_score, pn.priority_score,
               pn.engagement_count, pn.is_ai_discovered,
               COUNT(DISTINCT dc.id) AS contribution_count,
               COUNT(DISTINCT sp.id) AS solutions_count
        FROM problem_nodes pn
        LEFT JOIN discussion_threads dt ON dt.problem_id = pn.id
        LEFT JOIN discussion_contributions dc ON dc.thread_id = dt.id
        LEFT JOIN solution_projects sp ON sp.problem_id = pn.id
        WHERE pn.verified = true OR pn.is_ai_discovered = true
        GROUP BY pn.id
        ORDER BY pn.priority_score DESC, pn.impact_score DESC
        LIMIT :limit;
    """,

    "app_scaffold_stats": """
        -- Scaffold usage and deployment conversion rates
        SELECT
            scaffold_type,
            COUNT(*) AS total_generated,
            SUM(CASE WHEN deploy_status = 'deployed' THEN 1 ELSE 0 END) AS deployed,
            ROUND(
                SUM(CASE WHEN deploy_status = 'deployed' THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*),0) * 100, 1
            ) AS deploy_conversion_pct,
            AVG(estimated_build_hours) AS avg_estimated_hours,
            AVG(credits_consumed) AS avg_credits
        FROM app_scaffolds
        WHERE generated_at >= NOW() - INTERVAL '30 days'
        GROUP BY scaffold_type
        ORDER BY total_generated DESC;
    """,

    "document_generation_stats": """
        -- Document factory usage analytics
        SELECT document_type, audience, style,
               COUNT(*) AS documents_generated,
               AVG(word_count) AS avg_word_count,
               AVG(credits_consumed) AS avg_credits,
               SUM(CASE WHEN investor_mode THEN 1 ELSE 0 END) AS investor_mode_uses,
               COUNT(DISTINCT project_id) AS unique_projects
        FROM generated_documents
        WHERE generated_at >= NOW() - INTERVAL '30 days'
        GROUP BY document_type, audience, style
        ORDER BY documents_generated DESC;
    """,
}


# ============================================================================
# MIGRATION UTILITIES
# ============================================================================

# ── IP PROTECTION: Row-Level Security SQL ────────────────────────────────────
# Apply these after running alembic upgrade head.
# Ensures users can never read another project's ideas, documents, or outputs
# even through a misconfigured query.  The app connects as 'techit_app' role
# (not superuser) so RLS policies always apply.

RLS_POLICIES_SQL = """
-- ── Enable RLS on all sensitive tables ──────────────────────────────────────

ALTER TABLE projects                ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_outputs              ENABLE ROW LEVEL SECURITY;
ALTER TABLE idea_embeddings         ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_documents     ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_exports        ENABLE ROW LEVEL SECURITY;
ALTER TABLE solution_projects       ENABLE ROW LEVEL SECURITY;
ALTER TABLE solution_deployments    ENABLE ROW LEVEL SECURITY;
ALTER TABLE grant_applications      ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations             ENABLE ROW LEVEL SECURITY;
ALTER TABLE score_snapshots         ENABLE ROW LEVEL SECURITY;
ALTER TABLE investor_evi_snapshots  ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_ledger           ENABLE ROW LEVEL SECURITY;
ALTER TABLE paywall_hits            ENABLE ROW LEVEL SECURITY;

-- ── Project isolation: users see only their own projects ─────────────────────
-- current_setting('app.user_id') is set by the application per request.
-- FastAPI middleware: conn.execute("SET app.user_id = %s", [user_id])

CREATE POLICY project_owner_policy ON projects
    USING (owner_id = current_setting('app.user_id')::uuid);

-- ── AI outputs: users see only their own executions ──────────────────────────
CREATE POLICY ai_output_owner_policy ON ai_outputs
    USING (user_id = current_setting('app.user_id')::uuid);

-- ── Idea embeddings: strict project isolation ────────────────────────────────
-- Even admin queries on idea_embeddings are routed through project ownership.
CREATE POLICY idea_embedding_owner_policy ON idea_embeddings
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE owner_id = current_setting('app.user_id')::uuid
        )
    );

-- ── Generated documents: user can only see their own ────────────────────────
CREATE POLICY document_owner_policy ON generated_documents
    USING (user_id = current_setting('app.user_id')::uuid);

CREATE POLICY document_export_owner_policy ON document_exports
    USING (user_id = current_setting('app.user_id')::uuid);

-- ── Solution projects: creator-only unless explicitly shared ─────────────────
CREATE POLICY solution_owner_policy ON solution_projects
    USING (created_by = current_setting('app.user_id')::uuid);

-- ── Grant applications: creator-only ─────────────────────────────────────────
CREATE POLICY grant_owner_policy ON grant_applications
    USING (created_by = current_setting('app.user_id')::uuid);

-- ── Billing records: user can only see their own ledger ──────────────────────
CREATE POLICY credit_ledger_owner_policy ON credit_ledger
    USING (user_id = current_setting('app.user_id')::uuid);

-- ── Paywall hits: user can only see their own ────────────────────────────────
CREATE POLICY paywall_owner_policy ON paywall_hits
    USING (user_id = current_setting('app.user_id')::uuid);

-- ── Admin bypass: superuser and admin role bypass all RLS ───────────────────
-- The 'techit_admin' role is used only for scheduled jobs and admin panel.
GRANT techit_admin TO techit_app;  -- Admin inherits but does NOT bypass RLS
-- To bypass RLS for admin tasks use: SET LOCAL ROLE techit_superuser;

-- ── Marketplace exception: approved projects visible to all investors ─────────
-- Projects that have opted into investor visibility bypass the owner policy.
CREATE POLICY project_investor_visibility ON projects
    AS PERMISSIVE FOR SELECT
    USING (
        gsis_score > 0
        AND decay_factor > 0.5
        AND stage NOT IN ('idea')
        AND current_setting('app.user_role', true) = 'investor'
    );

-- ── Idea similarity search bypass: system-level leak detection only ───────────
-- The leak detection query (idea_similarity_check) runs as techit_system role,
-- which has BYPASSRLS privilege specifically for cross-project similarity checks.
-- This is the ONLY cross-project read permitted, and only for IP protection.
-- It never returns idea_text -- only project_id and similarity score.
"""


def apply_rls_policies(engine) -> None:
    """
    Apply Row-Level Security policies for cross-project data isolation.

    Run AFTER create_tables(). Requires superuser connection for ALTER TABLE.
    In production: run as part of the post-migration step, not as the app user.

    Usage:
        engine = create_engine(DATABASE_URL)
        create_tables(engine)
        setup_extensions(engine)
        apply_rls_policies(engine)
    """
    with engine.connect() as conn:
        # Execute each statement separately (psycopg2 doesn't support multi-statement)
        for stmt in RLS_POLICIES_SQL.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                try:
                    conn.execute(stmt + ";")
                except Exception as e:
                    # Policy may already exist -- safe to continue
                    if "already exists" not in str(e).lower():
                        print(f"⚠️  RLS statement skipped: {e}")
        print("✅ Row-Level Security policies applied")


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)
    print("✅ All TechIT tables created successfully.")


def setup_extensions(engine) -> None:
    with engine.connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        print("✅ Extensions: vector, uuid-ossp, pg_trgm")


# ============================================================================
# EQUITY & VESTING  (Collaborator value layer)
# ============================================================================
# Backs the collaborator Equity dashboard: per-startup grants, vesting schedules
# with cliffs, dilution protection, and cap-table snapshots. Money-as-ownership,
# distinct from cash payouts (see Payouts section below) and from billing credits.

class EquityGrant(Base):
    """
    A collaborator's equity grant in one project. Vesting is schedule-driven
    (years + cliff); vested_percent is snapshotted and also recomputable from
    grant_date + schedule. dilution_protected freezes already-vested equity.
    """
    __tablename__ = "equity_grants"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)

    equity_percent          = Column(Float, nullable=False)          # e.g. 0.8 (% of cap table)
    value_usd               = Column(DECIMAL(14, 2), default=0)      # current paper value
    vested_percent          = Column(Float, default=0)              # 0..100
    vesting_years           = Column(Integer, default=4)
    vesting_cliff_months    = Column(Integer, default=12)
    grant_date              = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    next_vest_date          = Column(TIMESTAMP)
    next_vest_delta_percent = Column(Float)                          # equity unlocked at next vest
    dilution_protected      = Column(Boolean, default=True)          # vested cannot be diluted w/o consent
    role_at_grant           = Column(String(120))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_equity_user",    "user_id"),
        Index("idx_equity_project", "project_id"),
        Index("idx_equity_user_project", "user_id", "project_id"),
    )


class CapTableEntry(Base):
    """One row of a project's cap table (Founders / Collaborator pool / You / ...)."""
    __tablename__ = "cap_table_entries"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    label       = Column(String(120), nullable=False)   # "Founders", "Investors", "You", ...
    percent     = Column(Float, nullable=False)
    holder_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # set when row is a specific user
    sort_order  = Column(Integer, default=0)
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_captable_project", "project_id", "sort_order"),)


class DilutionEvent(Base):
    """
    Audit trail of cap-table dilution events. Honors dilution protection: a
    collaborator's already-vested equity is shielded unless they consented.
    """
    __tablename__ = "dilution_events"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id    = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    description   = Column(Text)                       # "Series A new shares", etc.
    new_shares_percent = Column(Float, default=0)
    affected_user_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    consent_given      = Column(Boolean, default=False)
    protected_applied  = Column(Boolean, default=True) # vested equity shielded
    event_date    = Column(TIMESTAMP, default=datetime.utcnow)
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_dilution_project", "project_id", "event_date"),)


# ============================================================================
# PAYOUTS & EARNINGS  (Collaborator cash layer — money going OUT)
# ============================================================================
# Distinct from billing credits (money coming in). Backs the collaborator
# Earnings dashboard: per-project cash earned + pending, revenue share, and the
# payout ledger with withdrawals.

class CollaboratorEarning(Base):
    """Per-project cash earnings for a collaborator (earned + pending + rev share)."""
    __tablename__ = "collaborator_earnings"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    earned_usd            = Column(DECIMAL(14, 2), default=0)
    pending_usd           = Column(DECIMAL(14, 2), default=0)
    revenue_share_percent = Column(Float, default=0)
    contribution_note     = Column(Text)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_earning_user", "user_id"),
        Index("idx_earning_user_project", "user_id", "project_id"),
    )


class Payout(Base):
    """
    A single payout in the collaborator ledger. `status`:
      processing -> in flight to the destination account
      paid       -> settled
    """
    __tablename__ = "payouts"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    month_iso   = Column(String(7), nullable=False)        # "2026-05"
    amount_usd  = Column(DECIMAL(14, 2), nullable=False)
    status      = Column(String(20), default="processing") # processing | paid
    destination = Column(String(120))                      # masked acct, e.g. "•••1234"
    initiated_at = Column(TIMESTAMP, default=datetime.utcnow)
    settled_at   = Column(TIMESTAMP)

    __table_args__ = (Index("idx_payout_user", "user_id", "month_iso"),)


# ============================================================================
# INVESTOR — CAPITAL POOLS  (micro-funds, escrow, milestone-based release)
# ============================================================================
# Backs the investor Capital Pools dashboard: an investor funds a pool, capital
# is deployed across startups above a readiness threshold, and funds are released
# from escrow automatically as milestones are hit.

class CapitalPool(Base):
    """An investor micro-fund with deployment + milestone-release rules."""
    __tablename__ = "capital_pools"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name          = Column(String(160), nullable=False)
    total_capital_usd = Column(DECIMAL(16, 2), nullable=False)
    deployed_usd      = Column(DECIMAL(16, 2), default=0)
    funds_released_usd = Column(DECIMAL(16, 2), default=0)  # escrow released on milestones
    startups_count    = Column(Integer, default=0)
    milestones_hit    = Column(Integer, default=0)
    roi_simulation    = Column(Float, default=0)            # projected multiple, e.g. 3.2x
    # rules
    min_readiness     = Column(Integer, default=80)
    max_per_startup_percent = Column(Float, default=20)
    milestone_trigger = Column(Boolean, default=True)
    status        = Column(String(20), default="active")    # active | closed
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at    = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_pool_investor", "investor_id", "status"),)


class PoolMilestoneRelease(Base):
    """An escrow release event: capital paid out of a pool when a startup hits a milestone."""
    __tablename__ = "pool_milestone_releases"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id     = Column(UUID(as_uuid=True), ForeignKey("capital_pools.id"), nullable=False)
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"),     nullable=False)
    milestone   = Column(String(200))
    amount_usd  = Column(DECIMAL(16, 2), nullable=False)
    released     = Column(Boolean, default=False)           # False = held in escrow
    triggered_at = Column(TIMESTAMP)
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_release_pool", "pool_id", "released"),)


# ============================================================================
# INVESTOR — DEAL ROOMS  (cap table, term sheet, doc signing, negotiation)
# ============================================================================
# Backs the investor Deal Rooms list + detail: a secure per-deal workspace with
# negotiation stage tracking, a term-sheet simulator, milestone-based tranches,
# and document signing.

class DealRoom(Base):
    """A secure investor↔startup deal workspace with negotiation stage tracking."""
    __tablename__ = "deal_rooms"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    status       = Column(String(20), default="pending")   # active | pending | closed
    stage        = Column(String(60), default="Intro Call")
    days_open    = Column(Integer, default=0)
    messages     = Column(Integer, default=0)
    docs         = Column(Integer, default=0)
    last_activity = Column(String(40))                      # human "2h ago"
    encrypted    = Column(Boolean, default=True)
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at   = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_dealroom_investor", "investor_id", "status"),
        Index("idx_dealroom_project",  "project_id"),
    )


class TermSheet(Base):
    """Term-sheet simulator state for a deal room."""
    __tablename__ = "term_sheets"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_room_id  = Column(UUID(as_uuid=True), ForeignKey("deal_rooms.id"), nullable=False)
    valuation_usd = Column(DECIMAL(16, 2))
    investment_usd = Column(DECIMAL(16, 2))
    equity_percent = Column(Float)
    instrument    = Column(String(40), default="SAFE")      # SAFE | Equity | Convertible
    discount_percent = Column(Float, default=0)
    valuation_cap_usd = Column(DECIMAL(16, 2))
    extra_terms   = Column(JSON)                            # e.g. {"rights": "Observer"}
    updated_at    = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at    = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_termsheet_room", "deal_room_id"),)


class DealDocument(Base):
    """A document in a deal room (with signing status)."""
    __tablename__ = "deal_documents"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_room_id = Column(UUID(as_uuid=True), ForeignKey("deal_rooms.id"), nullable=False)
    name         = Column(String(200), nullable=False)
    status       = Column(String(20), default="draft")      # draft | ready | signed
    signed_by    = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    signed_at    = Column(TIMESTAMP)
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_dealdoc_room", "deal_room_id", "status"),)


# ============================================================================
# INVESTOR — DATA ROOMS  (document vault container + access control + sharing)
# ============================================================================
# Backs the investor Data Rooms list + detail: per-startup structured document
# repositories (6 sections), compliance/governance verification, and per-investor
# access grants (sharing).

class DataRoom(Base):
    """A per-startup structured document vault."""
    __tablename__ = "data_rooms"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id   = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    doc_count    = Column(Integer, default=0)
    compliance_verified     = Column(Boolean, default=False)
    ai_governance_verified  = Column(Boolean, default=False)
    sections     = Column(JSON)                            # ["Metrics Dashboard", ...]
    updated_label = Column(String(40), default="today")
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at   = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_dataroom_project", "project_id"),)


class DataRoomAccess(Base):
    """Per-investor access grant to a data room (sharing + audit)."""
    __tablename__ = "data_room_access"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_room_id = Column(UUID(as_uuid=True), ForeignKey("data_rooms.id"), nullable=False)
    investor_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"),      nullable=False)
    can_download = Column(Boolean, default=False)
    granted      = Column(Boolean, default=True)
    granted_at   = Column(TIMESTAMP, default=datetime.utcnow)
    revoked_at   = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_dataroom_access", "data_room_id", "investor_id"),
    )


# ============================================================================
# INVESTOR — REPUTATION  (mutual accountability: founders score investors too)
# ============================================================================
# Backs the investor Reputation dashboard. The platform scores investors the way
# it scores startups, creating balanced power dynamics: high-reputation investors
# earn early access to top deals.

class InvestorReputation(Base):
    """Composite investor reputation + its component metrics + leaderboard rank."""
    __tablename__ = "investor_reputation"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    composite_score = Column(Integer, default=0)            # 0..100
    month_change    = Column(Integer, default=0)
    # component metrics (0..100)
    response_speed       = Column(Integer, default=0)
    founder_rating       = Column(Integer, default=0)
    follow_through       = Column(Integer, default=0)
    value_add            = Column(Integer, default=0)
    portfolio_engagement = Column(Integer, default=0)
    # leaderboard
    rank             = Column(Integer)
    total_investors  = Column(Integer)
    percentile       = Column(Float)
    updated_at   = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at   = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_inv_reputation", "investor_id"),)


class InvestorReview(Base):
    """A founder's review of an investor (feeds founder_rating)."""
    __tablename__ = "investor_reviews"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    founder_name = Column(String(160))
    startup      = Column(String(160))
    rating       = Column(Integer)                          # 1..5
    comment      = Column(Text)
    review_date  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_inv_review", "investor_id", "review_date"),)


# ============================================================================
# WORKSPACES & PERSISTED ANALYSES  (Incubation → Workspace pipeline)
# ============================================================================
# Binds a founder's Workspace to a specific analyzed venture (project), and
# persists Incubation Hub pipeline output so it can flow into that workspace.
# Closes the gap where workspaces were a UI shell with no idea binding and the
# pipeline returned an ephemeral, unsaved blueprint.

class Workspace(Base):
    """A founder workspace bound to one analyzed venture (project)."""
    __tablename__ = "workspaces"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name        = Column(String(255), nullable=False)
    status      = Column(String(20), default="active")     # active | archived
    # Snapshot of the analysis that seeded this workspace (denormalized for fast load).
    seed_analysis_id = Column(UUID(as_uuid=True), ForeignKey("project_analyses.id"))
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at  = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_workspace_owner",   "owner_id", "status"),
        Index("idx_workspace_project", "project_id"),
    )


class ProjectAnalysis(Base):
    """
    A persisted Incubation Hub pipeline result for a project. Each run of the
    venture pipeline writes one row; the latest is what a workspace loads as
    context. This is the durable record the ephemeral blueprint never had.
    """
    __tablename__ = "project_analyses"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id  = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    owner_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    venture_name = Column(String(255))
    # Full compiled blueprint (unicorn/market/feasibility/strategy/finance/plan/tech...).
    blueprint   = Column(JSON, default={})
    # Headline scores lifted out for indexing/sorting.
    unicorn_potential_score = Column(Float, default=0.0)
    investment_score        = Column(Float, default=0.0)
    pivot_needed            = Column(Boolean, default=False)
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_analysis_project", "project_id", "created_at"),
        Index("idx_analysis_owner",   "owner_id"),
    )


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║            TECHIT DATABASE SCHEMA -- PRODUCTION READY        ║
╠══════════════════════════════════════════════════════════════╣
║ Core:        users, projects                                 ║
║ AI:          ai_prompts, ai_outputs, ai_audio_outputs        ║
║              prompt_metrics                                  ║
║ Billing:     credit_ledger, credit_purchases                 ║
║              paywall_hits, referral_events                   ║
║ Scoring:     score_snapshots, wcrs_history                   ║
║ Investor:    investor_evi_snapshots, investor_watchlist       ║
║              investor_alerts                                 ║
║ Evaluation:  evaluations                                     ║
║ Readiness:   readiness_tracker, readiness_milestones         ║
║              project_milestones                              ║
║ Training:    learner_profiles, personalised_curricula        ║
║              module_progress                                 ║
║ Matching:    matches                                         ║
║ Community:   feed_posts                                      ║
║ Org Sphere:  organizations, org_members                      ║
║ Vectors:     user_skill_embeddings, idea_embeddings          ║
║ Ops:         agent_execution_logs, event_logs                ║
║ Idea Hub:    problem_nodes, solution_projects                ║
║              discussion_threads, discussion_contributions    ║
║              solution_deployments, field_feedback            ║
║              impact_snapshots, grant_applications            ║
║ Documents:   generated_documents, document_exports           ║
║              document_templates                              ║
║ App Builder: app_scaffolds                                   ║
╠══════════════════════════════════════════════════════════════╣
║ Migration:                                                   ║
║   alembic upgrade head                                       ║
║   CREATE EXTENSION IF NOT EXISTS vector;                     ║
║   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";                ║
╚══════════════════════════════════════════════════════════════╝
""")
