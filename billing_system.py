"""
TECHIT -- HYBRID BILLING SYSTEM
================================
Module: billing_system.py
Layer:  Revenue Engine + Access Control

Core Principle
──────────────
TechIT must feel like a career decision, not a subscription.
People cancel streaming services. They do not cancel income,
reputation, or opportunity.

Two Billing Tracks -- Running Simultaneously
────────────────────────────────────────────
TRACK A -- SUBSCRIPTION
  Monthly or annual plan per role.
  Includes a monthly credit allocation.
  Unlocks feature tiers and paywalls.
  Best for: regular active users.

TRACK B -- PAY-AS-YOU-GO (PAYG)
  No monthly commitment.
  Buy credit packs that never expire.
  Each AI operation costs a fixed number of credits.
  Best for: occasional users, organisations on a per-project basis.

HYBRID RESOLUTION
  A subscriber ALSO holds PAYG credits.
  When subscription allocation exhausts, PAYG credits take over automatically.
  Subscribers always pay a lower per-credit rate than pure PAYG buyers.
  Resolution order: subscription credits first -> PAYG overflow.

Role-Based Pricing
──────────────────
  Founders     -> pay for execution survival and investor access
  Collaborators -> pay for career leverage and project income
  Organisations -> NO free tier -- every engagement is billable (primary cash engine)
  Investors    -> invite-only annual access, premium signal quality

Paywall Philosophy
──────────────────
  "Let them taste value, then block progress."
  Paywalls trigger at high-momentum moments:
    - Idea scored 80%+ -> block full roadmap
    - 3 collaborators matched -> block contact
    - Market tracker started -> block milestone detail
    - Investor viewed profile -> block reply

Contents
────────
  1.  Role and plan enumerations
  2.  PlanSpec dataclass (all 11 plans)
  3.  CreditOperation registry (all billable operations)
  4.  UserBillingState
  5.  HybridCreditEngine (subscription-first resolution)
  6.  PaywallEnforcementService (paywall hit logging + analytics)
  7.  BillingLedger (immutable event log)
  8.  ReferralEngine (viral growth rewards)
  9.  RevenueProjectionModel (90-day simulation)
 10.  Usage example
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

# Single module-level logger keeps the credit-event log line shape consistent
# across every resolve() outcome. Search prod logs for `credit_resolved` to
# see every paywall trigger / deduction in chronological order.
logger = structlog.get_logger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class BillingRole(Enum):
    FOUNDER      = "founder"
    COLLABORATOR = "collaborator"
    ORGANISATION = "organisation"
    INVESTOR     = "investor"


class FounderPlan(Enum):
    FREE_EXPLORER = "founder_free"      # $0
    BUILDER       = "founder_builder"   # $29/month
    SCALE         = "founder_scale"     # $99/month


class CollaboratorPlan(Enum):
    FREE_PROFILE  = "collab_free"       # $0
    PRO_BUILDER   = "collab_pro"        # $19/month
    ELITE_BUILDER = "collab_elite"      # $49/month


class OrganisationPlan(Enum):
    PROJECT_LAUNCH = "org_project"      # $299/project -- no free tier
    GROWTH         = "org_growth"       # $999/project
    ENTERPRISE     = "org_enterprise"   # Custom


class InvestorPlan(Enum):
    INVESTOR_ACCESS  = "investor_access"       # $1,500/year
    INSTITUTIONAL    = "investor_institutional" # $10,000+/year


class BillingEventType(Enum):
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
    TRIAL_STARTED          = "trial_started"
    TRIAL_CONVERTED        = "trial_converted"


# ============================================================================
# PLAN SPECIFICATIONS
# ============================================================================

@dataclass(frozen=True)
class PlanSpec:
    """
    Complete, immutable specification for one subscription plan.
    frozen=True: plans are constants, never mutated at runtime.
    """
    plan_id:             str
    role:                BillingRole
    display_name:        str
    price_monthly_usd:   float
    price_annual_usd:    float        # pre-applied annual discount
    monthly_credits:     int          # included with plan each month
    payg_credit_rate:    float        # USD per credit (subscribers get discount vs free)
    max_projects:        int          # -1 = unlimited
    max_team_members:    int
    features:            List[str]
    locked_features:     List[str]    # trigger upgrade prompts
    paywall_copy:        str
    upgrade_cta:         str
    psychology_note:     str          # internal -- why this tier converts


# ── FOUNDER PLANS ──────────────────────────────────────────────────────────

FOUNDER_FREE = PlanSpec(
    plan_id="founder_free", role=BillingRole.FOUNDER,
    display_name="Explorer (Free)",
    price_monthly_usd=0, price_annual_usd=0,
    monthly_credits=5, payg_credit_rate=0.50,
    max_projects=1, max_team_members=2,
    features=[
        "1 idea submission",
        "Basic AI idea evaluation (simplified score)",
        "View-only collaborator matches -- no contact",
        "Tour Guide daily check-in",
        "Dashboard GSIS overview",
        "Feed / Hangout (read-only)",
        "Basic profile",
        "Adaptive training curriculum preview",
    ],
    locked_features=[
        "Full unicorn analysis report",
        "Contact matched collaborators",
        "Market readiness tracker",
        "Execution roadmap",
        "Investor section visibility",
        "Business plan generator",
        "Tech stack design",
    ],
    paywall_copy="Your idea scored {score}% market readiness.\nUnlock the full roadmap, risks, and team recommendations.",
    upgrade_cta="Unlock Builder Plan -- $29/month",
    psychology_note="High score creates urgency. Founder must know more to survive.",
)

FOUNDER_BUILDER = PlanSpec(
    plan_id="founder_builder", role=BillingRole.FOUNDER,
    display_name="Builder ⭐",
    price_monthly_usd=29, price_annual_usd=290,   # save $58 (2 months free)
    monthly_credits=150, payg_credit_rate=0.25,
    max_projects=5, max_team_members=10,
    features=[
        "Unlimited idea submissions",
        "Full unicorn analysis + Dileep Rao benchmark",
        "Full AI scoring across all 15 dimensions",
        "GSIS dashboard with all component scores",
        "Team matching with contact access",
        "Market readiness tracker",
        "Workspace AI -- task suggestions and sprint planning",
        "Tour Guide with audio briefings",
        "Adaptive training curriculum (time-to-MVP engine)",
        "AI profile analysis",
        "Execution roadmap generation",
        "Tech stack design",
        "Feed / Hangout full access",
        "Org Sphere (basic)",
        "150 AI credits/month",
        "PAYG credit top-ups at $0.25/credit",
    ],
    locked_features=[
        "Full business plan generator",
        "Investor section visibility",
        "Market survey simulation",
        "Finance strategy report",
        "Investor readiness report",
        "EVI-I investor signal",
    ],
    paywall_copy="3 investors are tracking startups in your category.\nUnlock investor visibility and the full business plan.",
    upgrade_cta="Upgrade to Scale -- $99/month",
    psychology_note="Founders on Builder are executing. They upgrade when investors enter the picture.",
)

FOUNDER_SCALE = PlanSpec(
    plan_id="founder_scale", role=BillingRole.FOUNDER,
    display_name="Scale",
    price_monthly_usd=99, price_annual_usd=990,   # save $198
    monthly_credits=500, payg_credit_rate=0.18,
    max_projects=-1, max_team_members=-1,
    features=[
        "Everything in Builder",
        "Full business plan generator",
        "Executive summary generator",
        "Market survey simulation (AI synthetic research)",
        "Finance strategy report",
        "Investor readiness report",
        "Investor section -- full visibility to investors",
        "EVI-I investor execution signal",
        "Priority matching -- top-ranked in all results",
        "Advanced insights and export reports",
        "Org Sphere (full team intelligence)",
        "Market ready certification",
        "500 AI credits/month",
        "PAYG credit top-ups at $0.18/credit",
    ],
    locked_features=[],
    paywall_copy="",
    upgrade_cta="",
    psychology_note="Scale founders are fundraising. Remove all friction above this tier.",
)

# ── COLLABORATOR PLANS ─────────────────────────────────────────────────────

COLLAB_FREE = PlanSpec(
    plan_id="collab_free", role=BillingRole.COLLABORATOR,
    display_name="Profile (Free)",
    price_monthly_usd=0, price_annual_usd=0,
    monthly_credits=5, payg_credit_rate=0.50,
    max_projects=1, max_team_members=1,
    features=[
        "Basic profile",
        "Limited project visibility (view-only)",
        "Feed / Hangout (read-only)",
        "Training module previews",
    ],
    locked_features=[
        "Apply to paid projects",
        "Priority match placement",
        "Credibility score display",
        "Equity tracker",
        "Full adaptive training curriculum",
    ],
    paywall_copy="Paid projects available in your skill area.\nUpgrade to apply and get seen by serious founders.",
    upgrade_cta="Go Pro -- $19/month",
    psychology_note="Collaborators upgrade when they see peers earning from projects.",
)

COLLAB_PRO = PlanSpec(
    plan_id="collab_pro", role=BillingRole.COLLABORATOR,
    display_name="Pro Builder ⭐",
    price_monthly_usd=19, price_annual_usd=190,   # save $38
    monthly_credits=50, payg_credit_rate=0.30,
    max_projects=10, max_team_members=-1,
    features=[
        "Full profile with skills verification",
        "Priority match placement (ranked higher in results)",
        "Apply to unlimited paid projects",
        "Credibility score display on profile",
        "Adaptive training curriculum (full access)",
        "Feed / Hangout full access",
        "AI profile analysis + recommendations",
        "50 AI credits/month",
        "PAYG top-ups at $0.30/credit",
    ],
    locked_features=[
        "Verified badge",
        "Top placement (above Pro builders)",
        "Equity / revenue share tracking",
    ],
    paywall_copy="Unlock the Verified Builder badge and top placement.\nBe the first collaborator founders see.",
    upgrade_cta="Upgrade to Elite -- $49/month",
    psychology_note="Pro builders upgrade to Elite when competing for high-value projects.",
)

COLLAB_ELITE = PlanSpec(
    plan_id="collab_elite", role=BillingRole.COLLABORATOR,
    display_name="Elite Builder",
    price_monthly_usd=49, price_annual_usd=490,   # save $98
    monthly_credits=150, payg_credit_rate=0.22,
    max_projects=-1, max_team_members=-1,
    features=[
        "Everything in Pro",
        "Top placement in all match results",
        "Verified badge on profile",
        "Equity and revenue share tracker",
        "First access to premium projects",
        "Featured in monthly builder spotlight",
        "150 AI credits/month",
        "PAYG top-ups at $0.22/credit",
    ],
    locked_features=[],
    paywall_copy="",
    upgrade_cta="",
    psychology_note="Elite is the career achievement tier -- no paywalls above.",
)

# ── ORGANISATION PLANS ─────────────────────────────────────────────────────

ORG_PROJECT = PlanSpec(
    plan_id="org_project", role=BillingRole.ORGANISATION,
    display_name="Project Launch",
    price_monthly_usd=0, price_annual_usd=299,   # $299 per project -- no monthly
    monthly_credits=200, payg_credit_rate=0.20,
    max_projects=1, max_team_members=5,
    features=[
        "AI-scoped team assembly",
        "Milestone tracking",
        "Project workspace",
        "AI task management",
        "Delivery reporting",
        "200 AI credits per project",
    ],
    locked_features=[
        "Dedicated Project Manager",
        "SLA guarantee",
        "Priority talent pool",
    ],
    paywall_copy="Upgrade to Growth for a dedicated Project Manager and priority talent.",
    upgrade_cta="Upgrade to Growth -- $999/project",
    psychology_note="Orgs start here and upgrade after first successful delivery.",
)

ORG_GROWTH = PlanSpec(
    plan_id="org_growth", role=BillingRole.ORGANISATION,
    display_name="Growth ⭐",
    price_monthly_usd=0, price_annual_usd=999,
    monthly_credits=500, payg_credit_rate=0.15,
    max_projects=3, max_team_members=20,
    features=[
        "Everything in Project Launch",
        "Dedicated AI Project Manager",
        "Priority access to top-rated builders",
        "SLA: 48-hour team assembly",
        "Advanced AI progress reporting",
        "Compliance and governance reports",
        "500 AI credits per project",
        "Up to 3 concurrent projects",
    ],
    locked_features=[
        "White-label platform",
        "Custom integrations",
        "Unlimited concurrent projects",
    ],
    paywall_copy="Unlock Enterprise for white-label and unlimited concurrent projects.",
    upgrade_cta="Contact sales for Enterprise",
    psychology_note="Growth orgs have proven ROI. Enterprise is a relationship sale.",
)

ORG_ENTERPRISE = PlanSpec(
    plan_id="org_enterprise", role=BillingRole.ORGANISATION,
    display_name="Enterprise",
    price_monthly_usd=0, price_annual_usd=0,      # negotiated
    monthly_credits=999_999, payg_credit_rate=0.08,
    max_projects=-1, max_team_members=-1,
    features=[
        "Everything in Growth",
        "White-label platform",
        "Custom integrations and full API access",
        "Unlimited concurrent projects",
        "Dedicated customer success manager",
        "Custom compliance and reporting",
        "On-premise deployment option",
        "SLA: 24-hour team assembly",
        "Unlimited AI credits",
        "Priority AI model access",
    ],
    locked_features=[],
    paywall_copy="",
    upgrade_cta="",
    psychology_note="Enterprise is negotiated. Lead with ROI.",
)

# ── INVESTOR PLANS ─────────────────────────────────────────────────────────

INVESTOR_ACCESS = PlanSpec(
    plan_id="investor_access", role=BillingRole.INVESTOR,
    display_name="Investor Access",
    price_monthly_usd=0, price_annual_usd=1_500,   # $125/month equivalent
    monthly_credits=500, payg_credit_rate=0.15,
    max_projects=-1, max_team_members=1,
    features=[
        "Full deal flow dashboard",
        "AI-ranked startup discovery (GSIS + WCRS)",
        "EVI-I scores for all startups (6-dimensional)",
        "Watchlist with threshold alerts",
        "Startup evaluation reports",
        "Market readiness certifications view",
        "Direct intro requests",
        "AI investment signal analysis",
        "500 AI credits/year",
    ],
    locked_features=[
        "Portfolio monitoring dashboard",
        "Cohort analytics",
        "White-label reports",
    ],
    paywall_copy="Unlock portfolio monitoring and cohort-level analytics.",
    upgrade_cta="Upgrade to Institutional -- $10,000/year",
    psychology_note="Investors upgrade when managing 5+ startups simultaneously.",
)

INVESTOR_INSTITUTIONAL = PlanSpec(
    plan_id="investor_institutional", role=BillingRole.INVESTOR,
    display_name="Institutional",
    price_monthly_usd=0, price_annual_usd=10_000,
    monthly_credits=999_999, payg_credit_rate=0.05,
    max_projects=-1, max_team_members=-1,
    features=[
        "Everything in Investor Access",
        "Portfolio monitoring dashboard",
        "Cohort analytics (accelerator-level view)",
        "White-label investor reports",
        "API access for portfolio systems",
        "Custom scoring models",
        "Dedicated account manager",
        "Unlimited AI credits",
        "Real-time data freshness",
    ],
    locked_features=[],
    paywall_copy="",
    upgrade_cta="",
    psychology_note="Institutional is for VCs and accelerators managing 20+ companies.",
)

# ── PLAN REGISTRY ──────────────────────────────────────────────────────────

ALL_PLANS: Dict[str, PlanSpec] = {
    p.plan_id: p for p in [
        FOUNDER_FREE, FOUNDER_BUILDER, FOUNDER_SCALE,
        COLLAB_FREE, COLLAB_PRO, COLLAB_ELITE,
        ORG_PROJECT, ORG_GROWTH, ORG_ENTERPRISE,
        INVESTOR_ACCESS, INVESTOR_INSTITUTIONAL,
    ]
}

ROLE_DEFAULT_FREE: Dict[BillingRole, PlanSpec] = {
    BillingRole.FOUNDER:      FOUNDER_FREE,
    BillingRole.COLLABORATOR: COLLAB_FREE,
    BillingRole.ORGANISATION: ORG_PROJECT,
    BillingRole.INVESTOR:     INVESTOR_ACCESS,
}

# Plan upgrade hierarchy per role (used by permission resolver)
PLAN_HIERARCHY: Dict[BillingRole, List[str]] = {
    BillingRole.FOUNDER:      ["founder_free", "founder_builder", "founder_scale"],
    BillingRole.COLLABORATOR: ["collab_free", "collab_pro", "collab_elite"],
    BillingRole.ORGANISATION: ["org_project", "org_growth", "org_enterprise"],
    BillingRole.INVESTOR:     ["investor_access", "investor_institutional"],
}


# ============================================================================
# CREDIT OPERATION REGISTRY
# ============================================================================

@dataclass(frozen=True)
class CreditOperation:
    """A single AI operation with its credit cost, minimum plan, and paywall copy."""
    operation_id:    str
    display_name:    str
    credit_cost:     int
    min_plan_id:     str
    paywall_copy:    Optional[str]
    upgrade_cta:     Optional[str]


CREDIT_OPERATIONS: Dict[str, CreditOperation] = {
    "idea_diagnostic": CreditOperation(
        "idea_diagnostic", "Idea Diagnostic", 1, "founder_free", None, None),
    "unicorn_analysis": CreditOperation(
        "unicorn_analysis", "Unicorn Analysis (Full)", 2, "founder_builder",
        "Your idea scored {score}%.\nUnlock the full unicorn model, driver breakdown, and improvement roadmap.",
        "Unlock Builder Plan -- $29/month"),
    "market_intelligence": CreditOperation(
        "market_intelligence", "Market Intelligence", 2, "founder_builder",
        "Your target market has strong signals.\nUnlock the full TAM/SAM/SOM analysis and competitor map.",
        "Unlock Builder Plan -- $29/month"),
    "startup_strategy": CreditOperation(
        "startup_strategy", "Startup Strategy", 3, "founder_builder", None, None),
    "tech_stack_design": CreditOperation(
        "tech_stack_design", "Tech Stack Architecture", 2, "founder_builder", None, None),
    "execution_roadmap": CreditOperation(
        "execution_roadmap", "Execution Roadmap", 2, "founder_builder",
        "Estimated launch: {days} days.\nUnlock milestones, risks, and investor readiness pathway.",
        "Unlock Market Pathway -- $29/month"),
    "business_plan": CreditOperation(
        "business_plan", "Full Business Plan", 4, "founder_scale",
        "Your investor-grade business plan is ready to generate.\nUnlock Scale plan to export and share.",
        "Unlock Scale Plan -- $99/month"),
    "investor_readiness": CreditOperation(
        "investor_readiness", "Investor Readiness Report", 2, "founder_scale",
        "3 investors are tracking startups in your category.\nUnlock investor visibility and readiness scoring.",
        "Unlock Scale Plan -- $99/month"),
    "investor_evi": CreditOperation(
        "investor_evi", "EVI-I Investor Signal", 2, "founder_scale",
        "Your execution velocity is being watched by investors.\nUnlock the full EVI-I signal breakdown.",
        "Unlock Scale Plan -- $99/month"),
    "market_survey": CreditOperation(
        "market_survey", "Market Survey Simulation", 3, "founder_scale", None, None),
    "matching_contact": CreditOperation(
        "matching_contact", "Contact Matched Collaborator", 1, "founder_builder",
        "{count} collaborators matched your idea.\nUpgrade to connect and start building.",
        "Start Building Now -- $29/month"),
    "paid_project_access": CreditOperation(
        "paid_project_access", "Access Paid Projects", 0, "collab_pro",
        "Paid projects available in your skill area.\nUpgrade to apply and get seen by serious founders.",
        "Go Pro -- $19/month"),
    "full_pipeline": CreditOperation(
        "full_pipeline", "Full Venture Pipeline", 12, "founder_scale", None, None),
    "gsis_compute": CreditOperation(
        "gsis_compute", "GSIS Compute", 1, "founder_free", None, None),
    "adaptive_training": CreditOperation(
        "adaptive_training", "Adaptive Training Curriculum", 1, "founder_free", None, None),
    "trust_verify_founder": CreditOperation(
        "trust_verify_founder", "Trust Founder Verification", 1, "founder_free", None, None),
    "trust_verify_org": CreditOperation(
        "trust_verify_org", "Trust Organization Verification", 1, "founder_free", None, None),
    "trust_milestone_review": CreditOperation(
        "trust_milestone_review", "Trust Milestone Review", 1, "founder_free", None, None),
}


# ============================================================================
# USER BILLING STATE
# ============================================================================

@dataclass
class UserBillingState:
    """
    Complete billing state for a user at a point in time.
    Both subscription and PAYG credits tracked simultaneously.
    """
    user_id:                          str
    role:                             BillingRole
    plan_id:                          str
    plan_spec:                        PlanSpec
    subscription_credits_remaining:   int       # resets monthly
    subscription_resets_at:           datetime
    payg_credits_balance:             int       # never expires

    billing_cycle:            str       # "monthly" | "annual" | "per_project"
    subscription_started_at:  datetime
    next_invoice_at:          datetime

    credits_used_this_period: int   = 0
    usd_spent_this_period:    float = 0.0

    @property
    def total_credits_available(self) -> int:
        return self.subscription_credits_remaining + self.payg_credits_balance


# ============================================================================
# HYBRID CREDIT RESOLUTION ENGINE
# ============================================================================

@dataclass
class CreditResolutionResult:
    """Result of resolving one credit operation against a user's billing state."""
    approved:               bool
    operation_id:           str
    credit_cost:            int
    from_subscription:      int
    from_payg:              int
    credits_remaining_after: int
    usd_cost_this_operation: float
    paywall_triggered:      bool          = False
    paywall_copy:           Optional[str] = None
    upgrade_cta:            Optional[str] = None
    upgrade_plan_id:        Optional[str] = None
    required_min_plan:      Optional[str] = None


class HybridCreditEngine:
    """
    Resolves credit availability across subscription + PAYG simultaneously.

    Resolution order (always subscription first):
      1. Check plan permission (is operation allowed on this plan?)
      2. Check total credit availability (subscription + PAYG combined)
      3. Deduct from subscription_credits_remaining first
      4. Overflow into payg_credits_balance if subscription exhausted
      5. If total insufficient -> paywall with upgrade prompt

    Guarantees:
      - Subscribers never pay PAYG rates until allocation exhausted
      - PAYG users never see a paywall if they have purchased credits
      - Every deduction is split into from_subscription + from_payg for ledger
    """

    def resolve(
        self,
        state:        UserBillingState,
        operation_id: str,
        context_vars: Optional[Dict[str, Any]] = None,
    ) -> CreditResolutionResult:
        """
        Resolve whether a user can proceed with an operation and compute
        exactly how credits will be deducted.
        """
        op = CREDIT_OPERATIONS.get(operation_id)
        if not op:
            logger.warning(
                "credit_resolved", outcome="unknown_operation",
                user_id=state.user_id, plan_id=state.plan_id,
                operation_id=operation_id, approved=False, paywall_triggered=True,
            )
            return CreditResolutionResult(
                approved=False, operation_id=operation_id, credit_cost=0,
                from_subscription=0, from_payg=0,
                credits_remaining_after=state.total_credits_available,
                usd_cost_this_operation=0,
                paywall_triggered=True, paywall_copy="Unknown operation.",
            )

        # Step 1 -- plan permission
        if not self._plan_permits(state.plan_id, op.min_plan_id):
            copy = self._render_copy(op.paywall_copy, context_vars)
            logger.info(
                "credit_resolved", outcome="plan_denied",
                user_id=state.user_id, plan_id=state.plan_id,
                operation_id=operation_id, credit_cost=op.credit_cost,
                required_min_plan=op.min_plan_id,
                approved=False, paywall_triggered=True,
            )
            return CreditResolutionResult(
                approved=False, operation_id=operation_id, credit_cost=op.credit_cost,
                from_subscription=0, from_payg=0,
                credits_remaining_after=state.total_credits_available,
                usd_cost_this_operation=0,
                paywall_triggered=True, paywall_copy=copy,
                upgrade_cta=op.upgrade_cta,
                upgrade_plan_id=op.min_plan_id,
                required_min_plan=op.min_plan_id,
            )

        # Step 2 -- credit sufficiency
        total = state.total_credits_available
        cost  = op.credit_cost
        if total < cost:
            logger.info(
                "credit_resolved", outcome="insufficient_credits",
                user_id=state.user_id, plan_id=state.plan_id,
                operation_id=operation_id, credit_cost=cost,
                credits_remaining=total,
                approved=False, paywall_triggered=True,
            )
            return CreditResolutionResult(
                approved=False, operation_id=operation_id, credit_cost=cost,
                from_subscription=0, from_payg=0,
                credits_remaining_after=total,
                usd_cost_this_operation=0,
                paywall_triggered=True,
                paywall_copy=(
                    f"This operation costs {cost} credit(s). "
                    f"You have {total} remaining.\n"
                    "Top up with a credit pack or upgrade your plan."
                ),
                upgrade_cta="Buy Credits",
            )

        # Step 3 -- subscription-first deduction
        if state.subscription_credits_remaining >= cost:
            from_sub  = cost
            from_payg = 0
        else:
            from_sub  = state.subscription_credits_remaining
            from_payg = cost - from_sub

        usd_cost  = round(from_payg * state.plan_spec.payg_credit_rate, 4)
        remaining = state.total_credits_available - cost

        logger.info(
            "credit_resolved", outcome="approved",
            user_id=state.user_id, plan_id=state.plan_id,
            operation_id=operation_id, credit_cost=cost,
            from_subscription=from_sub, from_payg=from_payg,
            credits_remaining_after=remaining,
            usd_cost_this_operation=usd_cost,
            approved=True, paywall_triggered=False,
        )
        return CreditResolutionResult(
            approved=True, operation_id=operation_id, credit_cost=cost,
            from_subscription=from_sub, from_payg=from_payg,
            credits_remaining_after=remaining,
            usd_cost_this_operation=usd_cost,
        )

    def _plan_permits(self, user_plan_id: str, required_plan_id: str) -> bool:
        """Return True if user's plan meets or exceeds required plan."""
        for hierarchy in PLAN_HIERARCHY.values():
            if user_plan_id in hierarchy and required_plan_id in hierarchy:
                return hierarchy.index(user_plan_id) >= hierarchy.index(required_plan_id)
        # Enterprise always passes
        if user_plan_id == "org_enterprise":
            return True
        # Free plan passes for free-tier operations
        if required_plan_id == "founder_free" and user_plan_id in ALL_PLANS:
            return True
        return False

    def _render_copy(
        self, template: Optional[str], context: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        if not template:
            return None
        if context:
            try:
                return template.format(**context)
            except (KeyError, ValueError):
                return template
        return template


# ============================================================================
# PAYWALL ENFORCEMENT SERVICE
# ============================================================================

@dataclass
class PaywallHit:
    """Recorded every time a user hits a paywall -- analytics + A/B testing."""
    paywall_id:       str
    user_id:          str
    role:             BillingRole
    plan_id:          str
    operation_id:     str
    paywall_copy:     str
    upgrade_cta:      str
    upgrade_plan_id:  Optional[str]
    context_vars:     Dict[str, Any]
    hit_at:           datetime = field(default_factory=datetime.utcnow)
    converted:        bool     = False
    converted_at:     Optional[datetime] = None


class PaywallEnforcementService:
    """
    Enforces paywalls at feature entry points across all TechIT sections.

    "Let them taste value, then block progress."

    High-conversion paywall moments:
      1. After idea scores ≥ 75%    -> block full roadmap
      2. After 3+ collaborators matched -> block contact
      3. After market tracker starts  -> block milestone detail
      4. After investor views profile -> block reply
      5. After collaborator applies   -> block project chat on free

    All hits logged for conversion-rate analytics.
    """

    def __init__(self) -> None:
        self.engine   = HybridCreditEngine()
        self.hit_log: List[PaywallHit] = []

    def check_and_enforce(
        self,
        state:        UserBillingState,
        operation_id: str,
        context_vars: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[PaywallHit]]:
        """
        Main gate. Returns (can_proceed, paywall_hit_or_None).
        Called before every feature requiring plan access or credits.
        """
        resolution = self.engine.resolve(state, operation_id, context_vars)
        if not resolution.approved:
            hit = PaywallHit(
                paywall_id=f"pw_{operation_id}_{state.plan_id}",
                user_id=state.user_id,
                role=state.role,
                plan_id=state.plan_id,
                operation_id=operation_id,
                paywall_copy=resolution.paywall_copy or "Upgrade to continue.",
                upgrade_cta=resolution.upgrade_cta or "Upgrade",
                upgrade_plan_id=resolution.upgrade_plan_id,
                context_vars=context_vars or {},
            )
            self.hit_log.append(hit)
            return False, hit
        return True, None

    def get_locked_ui_copy(
        self, operation_id: str, context_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Return paywall copy for a feature without checking state.
        Used to pre-render locked UI elements (greyed out with lock icon).
        """
        op = CREDIT_OPERATIONS.get(operation_id)
        if not op:
            return {"copy": "Upgrade to unlock.", "cta": "Upgrade"}
        copy = op.paywall_copy or "Upgrade to unlock this feature."
        if context_vars:
            try:
                copy = copy.format(**context_vars)
            except (KeyError, ValueError):
                pass
        return {
            "copy":            copy,
            "cta":             op.upgrade_cta or "Upgrade",
            "upgrade_plan_id": op.min_plan_id,
        }

    def conversion_analytics(self) -> Dict[str, Any]:
        """Summarise paywall conversion rates. Production: aggregated from DB."""
        total = len(self.hit_log)
        if total == 0:
            return {"total_hits": 0, "conversion_rate": 0, "by_operation": {}}
        converted = sum(1 for h in self.hit_log if h.converted)
        by_op: Dict[str, Dict] = {}
        for hit in self.hit_log:
            op = hit.operation_id
            if op not in by_op:
                by_op[op] = {"hits": 0, "conversions": 0}
            by_op[op]["hits"] += 1
            if hit.converted:
                by_op[op]["conversions"] += 1
        for op, d in by_op.items():
            d["conversion_rate"] = round(d["conversions"] / max(d["hits"], 1) * 100, 1)
        return {
            "total_hits":             total,
            "total_conversions":      converted,
            "overall_conversion_pct": round(converted / total * 100, 1),
            "by_operation":           by_op,
        }


# ============================================================================
# BILLING EVENT LEDGER
# ============================================================================

@dataclass
class BillingEvent:
    """Immutable billing event. Maps to credit_ledger table in database_schema.py."""
    event_id:          str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:           str = ""
    event_type:        BillingEventType = BillingEventType.CREDITS_DEDUCTED
    plan_id:           str = ""
    operation_id:      Optional[str] = None
    credits_delta:     int   = 0
    credits_after:     int   = 0
    from_subscription: int   = 0
    from_payg:         int   = 0
    usd_amount:        float = 0.0
    stripe_payment_id: Optional[str] = None
    description:       str   = ""
    metadata:          Dict[str, Any] = field(default_factory=dict)
    created_at:        datetime = field(default_factory=datetime.utcnow)


class BillingLedger:
    """Immutable audit trail. Production: maps to credit_ledger DB table."""

    def __init__(self) -> None:
        self._events: List[BillingEvent] = []

    def record(self, event: BillingEvent) -> None:
        self._events.append(event)

    def get_user_events(self, user_id: str) -> List[BillingEvent]:
        return [e for e in self._events if e.user_id == user_id]

    def monthly_summary(self, user_id: str) -> Dict[str, Any]:
        now         = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        events      = [e for e in self.get_user_events(user_id) if e.created_at >= month_start]
        deductions  = [e for e in events if e.credits_delta < 0]
        purchases   = [e for e in events if e.event_type == BillingEventType.CREDITS_PURCHASED]
        return {
            "user_id":                user_id,
            "period":                 month_start.strftime("%Y-%m"),
            "credits_consumed":       abs(sum(e.credits_delta for e in deductions)),
            "credits_purchased":      sum(e.credits_delta for e in purchases),
            "usd_spent_on_payg":      round(sum(e.usd_amount for e in deductions), 4),
            "usd_spent_on_purchases": round(sum(e.usd_amount for e in purchases), 2),
            "operations_run":         len(deductions),
        }


# ============================================================================
# REFERRAL ENGINE
# ============================================================================

class ReferralEngine:
    """
    Viral growth through referral rewards and viral locks.

    Reward structure:
      Invite collaborator -> +10 credibility pts + 5 PAYG credits
      Invite founder      -> +5 PAYG credits (both sides)
      Invite organisation -> $20 account credit (applied to next invoice)
      5 successful invites -> 1 free subscription month

    Viral locks:
      Advanced matching unlocks after inviting 2 collaborators.
      Leaderboard access unlocks after inviting 1 founder.
    """

    REWARDS: Dict[str, Dict[str, Any]] = {
        "invite_collaborator": {
            "credits": 5, "credibility_pts": 10, "usd_credit": 0,
            "description": "Invited a collaborator who joined",
        },
        "invite_founder": {
            "credits": 5, "credibility_pts": 5, "usd_credit": 0,
            "description": "Invited a founder who joined",
        },
        "invite_organisation": {
            "credits": 20, "credibility_pts": 20, "usd_credit": 20.00,
            "description": "Referred an organisation that started a project",
        },
        "five_successful_invites": {
            "credits": 0, "credibility_pts": 50, "usd_credit": 0, "free_months": 1,
            "description": "5 successful referrals -- 1 free subscription month",
        },
    }

    VIRAL_LOCKS: Dict[str, Dict[str, Any]] = {
        "advanced_matching": {
            "required_invites": 2, "required_role": "collaborator",
            "lock_copy": "Invite 2 collaborators to unlock advanced matching.",
            "unlock_benefit": "Advanced AI matching with explanation and risk analysis",
        },
        "leaderboard_access": {
            "required_invites": 1, "required_role": "founder",
            "lock_copy": "Invite 1 founder to unlock the community leaderboard.",
            "unlock_benefit": "Global startup leaderboard visibility",
        },
    }

    def compute_reward(self, action: str) -> Optional[Dict[str, Any]]:
        return self.REWARDS.get(action)

    def check_viral_lock(
        self, feature: str, invite_count: int
    ) -> Dict[str, Any]:
        lock = self.VIRAL_LOCKS.get(feature)
        if not lock:
            return {"locked": False}
        required = lock["required_invites"]
        if invite_count >= required:
            return {"locked": False, "unlock_benefit": lock["unlock_benefit"]}
        return {
            "locked":    True,
            "lock_copy": lock["lock_copy"],
            "needed":    required - invite_count,
        }


# ============================================================================
# REVENUE PROJECTION MODEL
# ============================================================================

class RevenueProjectionModel:
    """
    90-day acquisition and revenue simulation.

    Acquisition channels:
      A. Partnerships (universities, bootcamps, hubs) -> ~500K users
      B. Viral invites (3 invites/user × 40% conversion) -> ~240K users
      C. Content + social (Twitter, LinkedIn, YouTube)  -> ~100K users
      Total: ~840K–1M users

    Conversion by segment:
      Founders       300K × 25% paid = 75K @ $29 ARPU
      Collaborators  400K × 15% paid = 60K @ $19 ARPU
      Organisations   50K × 80% paid = 40K @ $299 ARPU
      Investors        5K × 70% paid = 3.5K @ $125 ARPU

    Total paying: ~178,500
    Blended ARPU: ~$88 (skewed up by organisation tier)
    MRR: ~$15.7M at full acquisition
    ARR: ~$188M
    Gross margin: ~96.5%
    """

    ACQUISITION = {
        "partnerships":   {"users": 500_000, "channel": "universities + bootcamps + hubs"},
        "viral_invites":  {"users": 240_000, "channel": "referral (3 invites × 40% conv)"},
        "content_social": {"users": 100_000, "channel": "Twitter, LinkedIn, YouTube"},
    }

    CONVERSION = {
        BillingRole.FOUNDER:      {"users": 300_000, "paid_pct": 0.25, "arpu": 29},
        BillingRole.COLLABORATOR: {"users": 400_000, "paid_pct": 0.15, "arpu": 19},
        BillingRole.ORGANISATION: {"users":  50_000, "paid_pct": 0.80, "arpu": 299},
        BillingRole.INVESTOR:     {"users":   5_000, "paid_pct": 0.70, "arpu": 125},
    }

    def project_90_day(self) -> Dict[str, Any]:
        total_users = sum(v["users"] for v in self.ACQUISITION.values())
        segments    = {}
        total_paying = 0
        total_mrr    = 0.0

        for role, d in self.CONVERSION.items():
            paying       = int(d["users"] * d["paid_pct"])
            mrr          = paying * d["arpu"]
            total_paying += paying
            total_mrr    += mrr
            segments[role.value] = {
                "total_users": d["users"],
                "paid_pct":    f"{d['paid_pct']*100:.0f}%",
                "paying":      paying,
                "arpu_usd":    d["arpu"],
                "mrr_usd":     mrr,
            }

        return {
            "total_users_90d":  total_users,
            "total_paying":     total_paying,
            "blended_arpu_usd": round(total_mrr / max(total_paying, 1), 2),
            "mrr_usd":          round(total_mrr, 0),
            "arr_usd":          round(total_mrr * 12, 0),
            "gross_margin_pct": 96.5,
            "segments":         segments,
            "acquisition_channels": self.ACQUISITION,
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_billing() -> None:
    engine  = HybridCreditEngine()
    paywall = PaywallEnforcementService()
    ledger  = BillingLedger()

    print("=" * 65)
    print("TECHIT -- HYBRID BILLING SYSTEM DEMO")
    print("=" * 65)

    # Scenario 1: Subscription nearly exhausted -- overflow to PAYG
    print("\n📋 Scenario 1: Builder subscription exhausted -> PAYG overflow")
    state1 = UserBillingState(
        user_id="founder_001", role=BillingRole.FOUNDER,
        plan_id="founder_builder", plan_spec=FOUNDER_BUILDER,
        subscription_credits_remaining=1,   # nearly gone
        subscription_resets_at=datetime.utcnow() + timedelta(days=12),
        payg_credits_balance=30,            # PAYG backup
        billing_cycle="monthly",
        subscription_started_at=datetime.utcnow() - timedelta(days=18),
        next_invoice_at=datetime.utcnow() + timedelta(days=12),
    )
    res = engine.resolve(state1, "unicorn_analysis")  # costs 2 credits
    print(f"   Operation:         unicorn_analysis (2 credits)")
    print(f"   Approved:          {res.approved}")
    print(f"   From subscription: {res.from_subscription} credit(s)")
    print(f"   From PAYG:         {res.from_payg} credit(s)")
    print(f"   PAYG USD charge:   ${res.usd_cost_this_operation:.4f}")
    print(f"   Credits after:     {res.credits_remaining_after}")

    # Scenario 2: Free founder hits paywall
    print("\n🔒 Scenario 2: Free Founder hits business plan paywall")
    state2 = UserBillingState(
        user_id="founder_002", role=BillingRole.FOUNDER,
        plan_id="founder_free", plan_spec=FOUNDER_FREE,
        subscription_credits_remaining=3,
        subscription_resets_at=datetime.utcnow() + timedelta(days=20),
        payg_credits_balance=0,
        billing_cycle="monthly",
        subscription_started_at=datetime.utcnow() - timedelta(days=10),
        next_invoice_at=datetime.utcnow() + timedelta(days=20),
    )
    can_proceed, hit = paywall.check_and_enforce(
        state2, "business_plan", {"score": 82}
    )
    print(f"   Can proceed:    {can_proceed}")
    if hit:
        print(f"   Paywall copy:   {hit.paywall_copy}")
        print(f"   Upgrade CTA:    {hit.upgrade_cta}")

    # Scenario 3: Pure PAYG -- subscription exhausted
    print("\n💳 Scenario 3: Pure PAYG run (subscription zeroed out)")
    state3 = UserBillingState(
        user_id="founder_003", role=BillingRole.FOUNDER,
        plan_id="founder_builder", plan_spec=FOUNDER_BUILDER,
        subscription_credits_remaining=0,   # exhausted
        subscription_resets_at=datetime.utcnow() + timedelta(days=2),
        payg_credits_balance=25,
        billing_cycle="monthly",
        subscription_started_at=datetime.utcnow() - timedelta(days=28),
        next_invoice_at=datetime.utcnow() + timedelta(days=2),
    )
    res3 = engine.resolve(state3, "market_intelligence")
    print(f"   From subscription: {res3.from_subscription}")
    print(f"   From PAYG:         {res3.from_payg} credits @ ${FOUNDER_BUILDER.payg_credit_rate}/credit")
    print(f"   PAYG USD charged:  ${res3.usd_cost_this_operation:.4f}")

    # Revenue projection
    print("\n📊 90-Day Revenue Projection")
    proj = RevenueProjectionModel().project_90_day()
    print(f"   Total users (90d): {proj['total_users_90d']:>10,}")
    print(f"   Total paying:      {proj['total_paying']:>10,}")
    print(f"   Blended ARPU:      ${proj['blended_arpu_usd']:>9.2f}")
    print(f"   MRR:               ${proj['mrr_usd']:>10,.0f}")
    print(f"   ARR:               ${proj['arr_usd']:>10,.0f}")
    print(f"   Gross Margin:      {proj['gross_margin_pct']}%")
    for role, seg in proj["segments"].items():
        print(f"   {role:14s}  {seg['total_users']:>7,} users  "
              f"-> {seg['paid_pct']:>4} paid  "
              f"-> {seg['paying']:>6,} paying  "
              f"-> ${seg['mrr_usd']:>10,.0f} MRR")

    print("=" * 65)


if __name__ == "__main__":
    example_billing()
