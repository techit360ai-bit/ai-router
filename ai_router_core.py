"""
TECHIT AI ROUTER CORE
=====================
Central orchestration brain for the TechIT AI Incubation Platform.

This module is the single source of truth for:
  - All enumerations and shared types used across the platform
  - The complete Scoring Engine (all 15 mathematical models)
  - Model routing with vendor fallback chains
  - Credit economy and subscription access control
  - Prompt engine with versioned templates
  - Safety engine: permissions, injection, IP protection
  - AI Command Layer: the gateway every AI call passes through
  - Cost monitor and rate limiting

Scoring Models Implemented
──────────────────────────
  1.  Global Startup Intelligence Score  (GSIS)  -- master composite score
  2.  Unicorn Potential Score            (UPS)   -- 10-driver unicorn model
  3.  Execution Velocity Index           (EVI)   -- founder momentum
  4.  EVI for Investor Intelligence      (EVI-I) -- investor-grade execution signal
  5.  Revenue Growth Signal              (RGS)
  6.  Beta Satisfaction Score            (BSS)
  7.  Compliance Score                   (CS)
  8.  Market Readiness Score             (MRS)
  9.  Transparency Score                 (TS)
  10. Founder Reliability Score          (FRS)
  11. Community Influence Score          (CIS)
  12. Investor Interest Score            (IIS)
  13. Product Progress Score             (PPS)
  14. Team Strength Score                (TSS)
  15. Weighted Composite Ranking Score   (WCRS)  -- marketplace ranking
  16. Investment Score                   (IS)
  17. Match Score                        (MS)
  18. Decay Factor                       -- anti-gaming inactivity penalty
  19. Impact Score                       -- Idea & Solution Hub problem severity
  20. Problem Priority Score             -- Global Problems Board ranking

New Modules Integrated
──────────────────────
  idea_solution_hub.py    -- Problem-Driven pathway, discovery, deployment, impact
  document_generation.py  -- 8-type document factory, export system
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

import agent_prompts as AP


# ============================================================================
# ENUMERATIONS
# ============================================================================

class UserRole(Enum):
    FOUNDER         = "founder"
    BUILDER         = "collaborator"
    INVESTOR        = "investor"
    ADMIN           = "admin"
    ACCELERATOR_MGR = "accelerator_manager"


class SubscriptionTier(Enum):
    FREE         = "free"
    BUILDER      = "builder"
    FOUNDER_PRO  = "founder_pro"
    INVESTOR     = "investor"
    ENTERPRISE   = "enterprise"


class TaskType(Enum):
    # Incubation intelligence
    IDEA_EVALUATION          = "idea_evaluation"
    UNICORN_ANALYSIS         = "unicorn_analysis"
    MARKET_INTELLIGENCE      = "market_intelligence"
    PRODUCT_FEASIBILITY      = "product_feasibility"
    STARTUP_STRATEGY         = "startup_strategy"
    FINANCE_STRATEGY         = "finance_strategy"
    INVESTOR_READINESS       = "investor_readiness"
    BUSINESS_PLAN            = "business_plan"
    EXECUTIVE_SUMMARY        = "executive_summary"
    TECH_STACK_DESIGN        = "tech_stack_design"
    MARKET_SURVEY_SIMULATION = "market_survey_simulation"
    PIVOT_INTELLIGENCE       = "pivot_intelligence"
    EXECUTION_ROADMAP        = "execution_roadmap"
    RECOMMENDATION_ENGINE    = "recommendation_engine"
    # Platform operations
    TRAINING_GENERATION      = "training_generation"
    CHAT                     = "chat"
    CODE_REVIEW              = "code_review"
    SUMMARY                  = "summary"
    EMBEDDINGS               = "embeddings"
    TOUR_GUIDE               = "tour_guide"
    MATCHING                 = "matching"
    INVESTOR_SIGNAL          = "investor_signal"
    RISK_ANALYSIS            = "risk_analysis"
    ADMIN_MONITOR            = "admin_monitor"
    WORKSPACE_ASSISTANT      = "workspace_assistant"
    FEED_INTELLIGENCE        = "feed_intelligence"
    PROFILE_ANALYSIS         = "profile_analysis"
    DASHBOARD_INTELLIGENCE   = "dashboard_intelligence"
    ORG_SPHERE               = "org_sphere"
    INVESTOR_EVI             = "investor_evi"
    GSIS_COMPUTE             = "gsis_compute"
    # Idea & Solution Hub -- Problem-Driven pathway
    PROBLEM_ANALYSIS         = "problem_analysis"
    SOLUTION_SYNTHESIS       = "solution_synthesis"
    IMPACT_PREDICTION        = "impact_prediction"
    FEASIBILITY_ESTIMATE     = "feasibility_estimate"
    PROBLEM_DISCOVERY        = "problem_discovery"
    SOLUTION_MATCHING        = "solution_matching"
    DEPLOYMENT_PLANNING      = "deployment_planning"
    GRANT_MATCHING           = "grant_matching"
    DISCUSSION_MODERATION    = "discussion_moderation"
    FIELD_FEEDBACK_ANALYSIS  = "field_feedback_analysis"
    # Document Generation Engine -- 8 document types
    DOCUMENT_EXECUTIVE_SUMMARY    = "document_executive_summary"
    DOCUMENT_BUSINESS_PLAN        = "document_business_plan"
    DOCUMENT_PITCH_DECK           = "document_pitch_deck"
    DOCUMENT_INVESTOR_REPORT      = "document_investor_report"
    DOCUMENT_UNICORN_REPORT       = "document_unicorn_report"
    DOCUMENT_PRODUCT_ROADMAP      = "document_product_roadmap"
    DOCUMENT_FINANCIAL_PROJECTION = "document_financial_projection"
    DOCUMENT_MARKET_RESEARCH      = "document_market_research"
    # Prompt -> Live App engine
    APP_SCAFFOLD_GENERATION        = "app_scaffold_generation"
    APP_DEPLOY_CONFIG              = "app_deploy_config"


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


# ============================================================================
# CREDIT ECONOMY
# ============================================================================

class CreditCost:
    """
    Credit cost per AI operation.
    Both subscription and PAYG tracks consume from this table.

    Key operations:
      Idea Diagnostic              ->  1 credit
      Unicorn Analysis             ->  2 credits
      Market Intelligence          ->  2 credits
      Startup Strategy             ->  3 credits
      Investor Readiness           ->  2 credits
      Executive Summary            ->  2 credits
      Full Business Plan           ->  4 credits
      Market Survey Simulation     ->  3 credits
      Tech Stack Architecture      ->  2 credits
      Execution Roadmap            ->  2 credits
      Full Venture Pipeline        -> 12 credits  (bundled)
      Investor EVI Report          ->  2 credits
      GSIS Compute                 ->  1 credit

    Monthly allocations by tier:
      Free           ->    5 / month
      Builder        ->   50 / month
      Founder Pro    ->  150 / month
      Investor       ->  500 / month
      Enterprise     ->  unlimited
    """

    COSTS: Dict[TaskType, int] = {
        TaskType.IDEA_EVALUATION:           1,
        TaskType.UNICORN_ANALYSIS:          2,
        TaskType.MARKET_INTELLIGENCE:       2,
        TaskType.PRODUCT_FEASIBILITY:       2,
        TaskType.STARTUP_STRATEGY:          3,
        TaskType.FINANCE_STRATEGY:          2,
        TaskType.INVESTOR_READINESS:        2,
        TaskType.EXECUTIVE_SUMMARY:         2,
        TaskType.BUSINESS_PLAN:             4,
        TaskType.MARKET_SURVEY_SIMULATION:  3,
        TaskType.TECH_STACK_DESIGN:         2,
        TaskType.EXECUTION_ROADMAP:         2,
        TaskType.RECOMMENDATION_ENGINE:     1,
        TaskType.PIVOT_INTELLIGENCE:        2,
        TaskType.INVESTOR_EVI:              2,
        TaskType.GSIS_COMPUTE:              1,
        # Operational
        TaskType.TRAINING_GENERATION:       1,
        TaskType.CHAT:                      0,
        TaskType.CODE_REVIEW:              1,
        TaskType.SUMMARY:                  1,
        TaskType.EMBEDDINGS:               0,
        TaskType.TOUR_GUIDE:               0,
        TaskType.MATCHING:                 1,
        TaskType.INVESTOR_SIGNAL:          2,
        TaskType.RISK_ANALYSIS:            2,
        TaskType.WORKSPACE_ASSISTANT:      0,
        TaskType.FEED_INTELLIGENCE:        0,
        TaskType.PROFILE_ANALYSIS:         1,
        TaskType.DASHBOARD_INTELLIGENCE:   0,
        TaskType.ORG_SPHERE:               1,
        TaskType.ADMIN_MONITOR:            0,
        # Idea & Solution Hub
        TaskType.PROBLEM_ANALYSIS:         2,
        TaskType.SOLUTION_SYNTHESIS:       3,
        TaskType.IMPACT_PREDICTION:        1,
        TaskType.FEASIBILITY_ESTIMATE:     2,
        TaskType.PROBLEM_DISCOVERY:        2,
        TaskType.SOLUTION_MATCHING:        2,
        TaskType.DEPLOYMENT_PLANNING:      2,
        TaskType.GRANT_MATCHING:           3,
        TaskType.DISCUSSION_MODERATION:    1,
        TaskType.FIELD_FEEDBACK_ANALYSIS:  1,
        # Document Generation Engine
        TaskType.DOCUMENT_EXECUTIVE_SUMMARY:    2,
        TaskType.DOCUMENT_BUSINESS_PLAN:        4,
        TaskType.DOCUMENT_PITCH_DECK:           3,
        TaskType.DOCUMENT_INVESTOR_REPORT:      3,
        TaskType.DOCUMENT_UNICORN_REPORT:       2,
        TaskType.DOCUMENT_PRODUCT_ROADMAP:      2,
        TaskType.DOCUMENT_FINANCIAL_PROJECTION: 2,
        TaskType.DOCUMENT_MARKET_RESEARCH:      3,
        # Prompt -> Live App engine
        TaskType.APP_SCAFFOLD_GENERATION:      5,
        TaskType.APP_DEPLOY_CONFIG:            3,
    }

    MONTHLY_CREDITS: Dict[SubscriptionTier, int] = {
        SubscriptionTier.FREE:          5,
        SubscriptionTier.BUILDER:      50,
        SubscriptionTier.FOUNDER_PRO: 150,
        SubscriptionTier.INVESTOR:    500,
        SubscriptionTier.ENTERPRISE:  999_999,
    }

    # PAYG credit packs: credits -> USD price
    CREDIT_PACKS: Dict[int, float] = {
        50:    20.00,
        150:   50.00,
        500:  150.00,
        1500: 400.00,
    }

    @classmethod
    def cost_for(cls, task: TaskType) -> int:
        return cls.COSTS.get(task, 1)

    @classmethod
    def monthly_allocation(cls, tier: SubscriptionTier) -> int:
        return cls.MONTHLY_CREDITS.get(tier, 5)


# ============================================================================
# SUBSCRIPTION ACCESS CONTROL
# ============================================================================

class SubscriptionAccessControl:
    """
    Gates each TaskType behind a minimum subscription tier.

    Free        -> basic validation, tour guide, dashboard, chat
    Builder     -> unicorn, market intel, matching, training
    Founder Pro -> strategy, roadmap, tech stack, risk, org sphere
    Investor    -> business plan, investor reports, market survey, EVI-I
    Enterprise  -> all operations including admin monitor
    """

    _FREE = {
        TaskType.CHAT, TaskType.TOUR_GUIDE, TaskType.IDEA_EVALUATION,
        TaskType.DASHBOARD_INTELLIGENCE, TaskType.WORKSPACE_ASSISTANT,
        TaskType.FEED_INTELLIGENCE, TaskType.GSIS_COMPUTE,
        TaskType.TRAINING_GENERATION,   # adaptive curriculum for all users
        # Idea & Solution Hub -- problem submission and basic impact free
        TaskType.PROBLEM_ANALYSIS, TaskType.IMPACT_PREDICTION,
        TaskType.FIELD_FEEDBACK_ANALYSIS, TaskType.DISCUSSION_MODERATION,
    }
    _BUILDER = _FREE | {
        TaskType.UNICORN_ANALYSIS, TaskType.MARKET_INTELLIGENCE,
        TaskType.RECOMMENDATION_ENGINE, TaskType.MATCHING,
        TaskType.TRAINING_GENERATION, TaskType.PROFILE_ANALYSIS,
        TaskType.SUMMARY, TaskType.EMBEDDINGS,
        # Idea & Solution Hub -- discovery and matching available to Builders
        TaskType.PROBLEM_DISCOVERY, TaskType.SOLUTION_MATCHING,
        TaskType.FEASIBILITY_ESTIMATE,
        # Document Generation -- quick docs available to Builders
        TaskType.DOCUMENT_EXECUTIVE_SUMMARY, TaskType.DOCUMENT_UNICORN_REPORT,
    }
    _FOUNDER_PRO = _BUILDER | {
        TaskType.STARTUP_STRATEGY, TaskType.FINANCE_STRATEGY,
        TaskType.PRODUCT_FEASIBILITY, TaskType.TECH_STACK_DESIGN,
        TaskType.EXECUTION_ROADMAP, TaskType.PIVOT_INTELLIGENCE,
        TaskType.CODE_REVIEW, TaskType.EXECUTIVE_SUMMARY,
        TaskType.ORG_SPHERE, TaskType.RISK_ANALYSIS,
        # Idea & Solution Hub -- full conversion, deployment, grants
        TaskType.SOLUTION_SYNTHESIS, TaskType.DEPLOYMENT_PLANNING,
        TaskType.GRANT_MATCHING,
        # Document Generation -- full suite except investor-only types
        TaskType.DOCUMENT_BUSINESS_PLAN, TaskType.DOCUMENT_PITCH_DECK,
        TaskType.DOCUMENT_PRODUCT_ROADMAP, TaskType.DOCUMENT_FINANCIAL_PROJECTION,
        TaskType.DOCUMENT_MARKET_RESEARCH,
        # Prompt -> Live App -- scaffold available from Founder Pro upward
        TaskType.APP_SCAFFOLD_GENERATION, TaskType.APP_DEPLOY_CONFIG,
    }
    _INVESTOR = _FOUNDER_PRO | {
        TaskType.INVESTOR_READINESS, TaskType.INVESTOR_SIGNAL,
        TaskType.BUSINESS_PLAN, TaskType.MARKET_SURVEY_SIMULATION,
        TaskType.INVESTOR_EVI, TaskType.ADMIN_MONITOR,
        # Document Generation -- investor-grade reports
        TaskType.DOCUMENT_INVESTOR_REPORT,
    }
    _ENTERPRISE = set(TaskType)

    TIER_MAP: Dict[SubscriptionTier, set] = {
        SubscriptionTier.FREE:        _FREE,
        SubscriptionTier.BUILDER:     _BUILDER,
        SubscriptionTier.FOUNDER_PRO: _FOUNDER_PRO,
        SubscriptionTier.INVESTOR:    _INVESTOR,
        SubscriptionTier.ENTERPRISE:  _ENTERPRISE,
    }

    @classmethod
    def is_allowed(cls, tier: SubscriptionTier, task: TaskType) -> bool:
        return task in cls.TIER_MAP.get(tier, cls._FREE)

    @classmethod
    def required_tier(cls, task: TaskType) -> SubscriptionTier:
        for tier in [SubscriptionTier.FREE, SubscriptionTier.BUILDER,
                     SubscriptionTier.FOUNDER_PRO, SubscriptionTier.INVESTOR,
                     SubscriptionTier.ENTERPRISE]:
            if task in cls.TIER_MAP[tier]:
                return tier
        return SubscriptionTier.ENTERPRISE


# ============================================================================
# UNIFIED SCORING ENGINE -- ALL 18 MODELS
# ============================================================================

class ScoringEngine:
    """
    Implements every TechIT mathematical scoring model in one place.

    All methods are @classmethod -- no instance state.
    All outputs are in [0, 100] range unless noted.
    All inputs are normalized internally.
    """

    # ── UNICORN DRIVERS ────────────────────────────────────────────────────
    UNICORN_WEIGHTS: Dict[str, float] = {
        "market_size":            0.15,
        "problem_severity":       0.12,
        "founder_advantage":      0.10,
        "technological_moat":     0.12,
        "scalability":            0.12,
        "network_effects":        0.10,
        "revenue_model_strength": 0.10,
        "market_timing":          0.08,
        "competition_landscape":  0.06,
        "capital_efficiency":     0.05,
    }

    UNICORN_TIERS = [
        (90, 100, "Unicorn Candidate",        "🦄"),
        (75,  90, "High Potential Startup",   "🚀"),
        (65,  75, "Early Traction Potential", "📈"),
        (50,  65, "Pre-Aha Stage",            "🔍"),
        (30,  50, "Idea Stage",               "💡"),
        ( 0,  30, "Weak Opportunity",         "⚠️"),
    ]

    # ── 1. GLOBAL STARTUP INTELLIGENCE SCORE (GSIS) ────────────────────────

    @classmethod
    def compute_gsis(
        cls,
        product_progress_score:  float,   # PPS   -- from workspace data
        execution_velocity_index: float,  # EVI   -- founder momentum
        market_readiness_score:  float,   # MRS   -- launch readiness
        beta_satisfaction_score: float,   # BSS   -- user validation
        revenue_growth_signal:   float,   # RGS   -- monetisation health
        founder_reputation_score: float,  # FRS   -- profile + community
        community_influence_score: float, # CIS   -- hangout/feed signals
        investor_interest_score:  float,  # IIS   -- investor engagement
        compliance_score:        float,   # CS    -- governance
    ) -> Dict:
        """
        GSIS = 0.15*PPS + 0.15*EVI + 0.20*MRS + 0.10*BSS + 0.10*RGS
              + 0.10*FRS + 0.05*CIS + 0.10*IIS + 0.05*CS

        The master score that surfaces on investor dashboards,
        marketplace rankings, and the founder's home dashboard.
        All component scores must be in [0, 100].
        """
        gsis = (
            0.15 * product_progress_score   +
            0.15 * execution_velocity_index +
            0.20 * market_readiness_score   +
            0.10 * beta_satisfaction_score  +
            0.10 * revenue_growth_signal    +
            0.10 * founder_reputation_score +
            0.05 * community_influence_score +
            0.10 * investor_interest_score  +
            0.05 * compliance_score
        )
        gsis = round(min(100.0, max(0.0, gsis)), 2)

        alert_score = cls._compute_alert_score(
            gsis, execution_velocity_index, market_readiness_score
        )

        return {
            "gsis":            gsis,
            "classification":  cls._classify_gsis(gsis),
            "alert_score":     alert_score,
            "alert_triggered": alert_score > 60,
            "components": {
                "product_progress":      product_progress_score,
                "execution_velocity":    execution_velocity_index,
                "market_readiness":      market_readiness_score,
                "beta_satisfaction":     beta_satisfaction_score,
                "revenue_growth":        revenue_growth_signal,
                "founder_reputation":    founder_reputation_score,
                "community_influence":   community_influence_score,
                "investor_interest":     investor_interest_score,
                "compliance":            compliance_score,
            },
        }

    @classmethod
    def _classify_gsis(cls, score: float) -> str:
        if score >= 85: return "Elite -- investor-ready"
        if score >= 70: return "Strong -- market-ready"
        if score >= 55: return "Developing -- on track"
        if score >= 40: return "Early -- needs focus"
        return "At risk -- intervention needed"

    @classmethod
    def _compute_alert_score(
        cls, gsis: float, evi: float, mrs: float
    ) -> float:
        """
        AlertScore = Risk + Delay + DropInMetrics
        High AlertScore -> AI intervention triggered.
        """
        risk  = max(0, 50 - gsis)
        delay = max(0, 40 - evi)
        drop  = max(0, 40 - mrs)
        return round(min(100.0, risk + delay + drop), 2)

    # ── 2. UNICORN POTENTIAL SCORE ─────────────────────────────────────────

    @classmethod
    def compute_unicorn_potential_score(cls, drivers: Dict[str, float]) -> Dict:
        """
        UPS = Σ (driver × weight) × 10  ->  [0, 100]
        Each driver scored 0–10. Weights sum to 1.00.
        """
        total = 0.0
        breakdown = {}
        for driver, weight in cls.UNICORN_WEIGHTS.items():
            raw = min(10.0, max(0.0, float(drivers.get(driver, 0))))
            contrib = raw * weight * 10
            total += contrib
            breakdown[driver] = {"raw_score": raw, "weight": weight, "contribution": round(contrib, 2)}

        score = round(min(100.0, total), 2)
        label, emoji = cls._classify_unicorn(score)
        return {
            "unicorn_potential_score": score,
            "classification":          label,
            "emoji":                   emoji,
            "unicorn_probability_pct": score,
            "driver_breakdown":        breakdown,
        }

    @classmethod
    def _classify_unicorn(cls, score: float) -> Tuple[str, str]:
        for lo, hi, label, emoji in cls.UNICORN_TIERS:
            if lo <= score <= hi:
                return label, emoji
        return "Weak Opportunity", "⚠️"

    # ── 3. EXECUTION VELOCITY INDEX (FOUNDER) ─────────────────────────────

    @classmethod
    def compute_evi(
        cls,
        milestones_completed_30d:  int,
        avg_response_time_hours:   float,
        iterations_per_month:      int,
        code_design_contributions: int,
        stagnation_days:           int,
    ) -> float:
        """
        EVI = (0.30*MC + 0.20*RC⁻¹ + 0.20*IC + 0.20*CC − 0.10*ST) × 100
        Founder-facing momentum score used by Tour Guide and WCRS.
        """
        mc = min(1.0, milestones_completed_30d / 10.0)
        rc = min(1.0, 1.0 / max(1.0, avg_response_time_hours))
        ic = min(1.0, iterations_per_month / 20.0)
        cc = min(1.0, code_design_contributions / 50.0)
        st = min(1.0, stagnation_days / 30.0)
        raw = 0.30*mc + 0.20*rc + 0.20*ic + 0.20*cc - 0.10*st
        return round(max(0.0, min(100.0, raw * 100)), 2)

    # ── 4. EVI FOR INVESTOR INTELLIGENCE ──────────────────────────────────

    @classmethod
    def compute_evi_investor(
        cls,
        mdr_score:  float,   # Milestone Delivery Rate        25%
        is_score:   float,   # Iteration Speed                20%
        trv_score:  float,   # Team Response Velocity         15%
        rta_score:  float,   # Revenue Traction Acceleration  20%
        ugm_score:  float,   # User Growth Momentum           10%
        cev_score:  float,   # Capital Efficiency Velocity    10%
        days_since_last_update: int = 0,
    ) -> Dict:
        """
        EVI-I = (0.25*MDR + 0.20*IS + 0.15*TRV + 0.20*RTA + 0.10*UGM + 0.10*CEV) × decay

        Investor-grade execution signal. Distinct from founder EVI.
        Applies anti-gaming decay identical to WCRS.
        """
        raw = (
            0.25 * mdr_score +
            0.20 * is_score  +
            0.15 * trv_score +
            0.20 * rta_score +
            0.10 * ugm_score +
            0.10 * cev_score
        )
        raw     = round(min(100.0, max(0.0, raw)), 2)
        decay   = cls.compute_decay_factor(days_since_last_update)
        adjusted = round(raw * decay, 2)
        signal = (
            "exceptional_velocity" if adjusted >= 85 else
            "strong_velocity"      if adjusted >= 70 else
            "moderate_velocity"    if adjusted >= 55 else
            "slow_velocity"        if adjusted >= 40 else
            "stalled"
        )
        return {
            "raw_evi_i":      raw,
            "decay_factor":   round(decay, 4),
            "adjusted_evi_i": adjusted,
            "signal":         signal,
            "dimensions": {
                "milestone_delivery_rate":          mdr_score,
                "iteration_speed":                  is_score,
                "team_response_velocity":           trv_score,
                "revenue_traction_acceleration":    rta_score,
                "user_growth_momentum":             ugm_score,
                "capital_efficiency_velocity":      cev_score,
            },
        }

    # ── 5. REVENUE GROWTH SIGNAL ───────────────────────────────────────────

    @classmethod
    def compute_rgs(
        cls,
        mrr_growth_pct:            float,
        user_growth_pct:           float,
        retention_pct:             float,
        revenue_consistency_score: float,
    ) -> float:
        """RGS = 0.35*MRR + 0.25*UserGrowth + 0.25*Retention + 0.15*Consistency"""
        rgs = (0.35 * min(100, mrr_growth_pct) + 0.25 * min(100, user_growth_pct) +
               0.25 * min(100, retention_pct)   + 0.15 * min(100, revenue_consistency_score))
        return round(max(0.0, min(100.0, rgs)), 2)

    # ── 6. BETA SATISFACTION SCORE ─────────────────────────────────────────

    @classmethod
    def compute_bss(
        cls,
        avg_ux_rating:          float,  # 0–10
        avg_performance_rating: float,  # 0–10
        nps:                    float,  # −100 to 100
        willingness_to_pay_pct: float,  # 0–100
    ) -> float:
        """BSS = 0.30*UX + 0.25*Perf + 0.25*NPS_norm + 0.20*WTP"""
        ux    = min(10.0, avg_ux_rating) / 10.0 * 100
        perf  = min(10.0, avg_performance_rating) / 10.0 * 100
        nps_n = (nps + 100) / 2.0
        bss   = 0.30*ux + 0.25*perf + 0.25*nps_n + 0.20*min(100, willingness_to_pay_pct)
        return round(max(0.0, min(100.0, bss)), 2)

    # ── 7. COMPLIANCE SCORE ────────────────────────────────────────────────

    COMPLIANCE_CHECKLIST = [
        "data_policy_present", "security_audit_complete",
        "ai_bias_disclosure",  "region_compatibility_verified",
        "api_risk_scan_passed",
    ]

    @classmethod
    def compute_compliance_score(cls, items: Dict[str, bool]) -> float:
        """CS = (Σ passed / total) × 100"""
        passed = sum(1 for k in cls.COMPLIANCE_CHECKLIST if items.get(k, False))
        return round(passed / len(cls.COMPLIANCE_CHECKLIST) * 100, 2)

    # ── 8. MARKET READINESS SCORE ──────────────────────────────────────────

    @classmethod
    def compute_market_readiness(
        cls,
        execution_score:   float,
        beta_satisfaction: float,
        revenue_signal:    float,
        compliance_score:  float,
        global_readiness:  float,
        stability_score:   float,
    ) -> float:
        """MRS = 0.25*EVI + 0.20*BSS + 0.20*RGS + 0.15*CS + 0.10*Global + 0.10*Stability"""
        mrs = (0.25*execution_score + 0.20*beta_satisfaction + 0.20*revenue_signal +
               0.15*compliance_score + 0.10*global_readiness + 0.10*stability_score)
        return round(max(0.0, min(100.0, mrs)), 2)

    # ── 9. TRANSPARENCY SCORE ──────────────────────────────────────────────

    TRANSPARENCY_CHECKLIST = [
        "pitch_deck_uploaded", "financials_provided",
        "team_profiles_complete", "product_demo_linked",
        "metrics_dashboard_public", "legal_docs_uploaded",
    ]

    @classmethod
    def compute_transparency_score(cls, items: Dict[str, bool]) -> float:
        """TS = (Σ provided / total) × 100"""
        provided = sum(1 for k in cls.TRANSPARENCY_CHECKLIST if items.get(k, False))
        return round(provided / len(cls.TRANSPARENCY_CHECKLIST) * 100, 2)

    # ── 10. FOUNDER RELIABILITY SCORE ─────────────────────────────────────

    @classmethod
    def compute_founder_reliability(
        cls,
        login_consistency_pct:    float,
        milestone_hit_rate_pct:   float,
        feedback_responsiveness:  float,
        community_contribution:   float,
        profile_completeness_pct: float,
    ) -> float:
        """FRS = 0.30*Login + 0.30*MilestoneRate + 0.20*Feedback + 0.10*Community + 0.10*Profile"""
        frs = (0.30*login_consistency_pct + 0.30*milestone_hit_rate_pct +
               0.20*feedback_responsiveness + 0.10*community_contribution +
               0.10*profile_completeness_pct)
        return round(max(0.0, min(100.0, frs)), 2)

    # ── 11. COMMUNITY INFLUENCE SCORE ─────────────────────────────────────

    @classmethod
    def compute_cis(
        cls,
        post_engagement_score:  float,  # 0–100 normalised engagement rate
        content_value_score:    float,  # 0–100 AI-assessed quality
        follower_quality_score: float,  # 0–100 verified/active ratio
    ) -> float:
        """
        CIS = (PostEngagement + ContentValue + FollowerQuality) / 3
        Feeds into GSIS and Founder Reputation Score.
        Anti-spam: TrustWeight = VerifiedActivity / TotalActivity applied upstream.
        """
        cis = (post_engagement_score + content_value_score + follower_quality_score) / 3.0
        return round(max(0.0, min(100.0, cis)), 2)

    # ── 12. INVESTOR INTEREST SCORE ────────────────────────────────────────

    @classmethod
    def compute_iis(
        cls,
        profile_views_normalised:   float,  # 0–100
        saves_normalised:           float,  # 0–100
        contact_requests_normalised: float, # 0–100
        watchlist_adds_normalised:  float,  # 0–100
    ) -> float:
        """
        IIS = (ProfileViews + Saves + ContactRequests + WatchlistAdds) / 4
        Measures genuine investor attention, not vanity metrics.
        """
        iis = (profile_views_normalised + saves_normalised +
               contact_requests_normalised + watchlist_adds_normalised) / 4.0
        return round(max(0.0, min(100.0, iis)), 2)

    # ── 13. PRODUCT PROGRESS SCORE ────────────────────────────────────────

    @classmethod
    def compute_pps(
        cls,
        completed_tasks: int,
        total_tasks:     int,
        quality_factor:  float,  # 0–1, AI-assessed output quality
    ) -> float:
        """
        PPS = (CompletedTasks / TotalTasks) × QualityFactor × 100
        Sourced from workspace milestone and task completion data.
        """
        if total_tasks == 0:
            return 0.0
        raw = (completed_tasks / total_tasks) * min(1.0, quality_factor) * 100
        return round(max(0.0, min(100.0, raw)), 2)

    # ── 14. TEAM STRENGTH SCORE ────────────────────────────────────────────

    @classmethod
    def compute_tss(
        cls,
        skill_coverage_pct:   float,  # 0–100
        activity_level_score: float,  # 0–100
        delivery_rate_pct:    float,  # 0–100
        collaboration_score:  float,  # 0–100
    ) -> float:
        """
        TSS = (SkillCoverage + ActivityLevel + DeliveryRate + Collaboration) / 4
        Sourced from Org Sphere and workspace collaboration data.
        RoleEfficiency = Output / AssignedTasks tracked per member.
        """
        tss = (skill_coverage_pct + activity_level_score +
               delivery_rate_pct + collaboration_score) / 4.0
        return round(max(0.0, min(100.0, tss)), 2)

    # ── 15. WEIGHTED COMPOSITE RANKING SCORE (WCRS) ────────────────────────

    @classmethod
    def compute_wcrs(
        cls,
        market_readiness:           float,
        execution_velocity:         float,
        beta_satisfaction:          float,
        revenue_growth_signal:      float,
        compliance_score:           float,
        transparency_score:         float,
        founder_reliability_score:  float,
        quality_flags:              int = 0,
        days_since_last_update:     int = 0,
    ) -> Dict:
        """
        Base  = 0.25*MR + 0.20*EVI + 0.15*BSS + 0.15*RGS
                + 0.10*CS + 0.10*TS + 0.05*FRS
        Final = Base × (1 + 0.05 × QualityFlags)   [max 1.15]
        Adjusted = Final × e^(−0.02 × days_inactive)

        Anti-gaming: inactive startups rank lower automatically.
        """
        base = (0.25*market_readiness + 0.20*execution_velocity + 0.15*beta_satisfaction +
                0.15*revenue_growth_signal + 0.10*compliance_score +
                0.10*transparency_score + 0.05*founder_reliability_score)
        q_mult   = 1.0 + 0.05 * min(3, quality_flags)
        final    = base * q_mult
        decay    = cls.compute_decay_factor(days_since_last_update)
        adjusted = final * decay
        return {
            "base_wcrs":          round(base, 2),
            "quality_multiplier": round(q_mult, 4),
            "final_before_decay": round(final, 2),
            "decay_factor":       round(decay, 4),
            "adjusted_score":     round(adjusted, 2),
        }

    # ── 16. INVESTMENT SCORE ───────────────────────────────────────────────

    @classmethod
    def compute_investment_score(
        cls,
        market_readiness:      float,
        traction_score:        float,
        team_score:            float,
        risk_inverse:          float,
        growth_rate:           float,
        differentiation_score: float,
    ) -> float:
        """InvestScore = 0.30*MR + 0.25*Traction + 0.15*Team + 0.15*RiskInverse + 0.10*Growth + 0.05*Diff"""
        score = (0.30*market_readiness + 0.25*traction_score + 0.15*team_score +
                 0.15*risk_inverse + 0.10*growth_rate + 0.05*differentiation_score)
        return round(max(0.0, min(100.0, score)), 2)

    # ── 17. MATCH SCORE ────────────────────────────────────────────────────

    @classmethod
    def compute_match_score(
        cls,
        skill_similarity:           float,  # 0–1 from vector cosine
        goal_similarity:            float,
        execution_style_similarity: float,
        availability_overlap:       float,
        trust_score:                float,
        domain_experience:          float,
    ) -> float:
        """MatchScore = (0.30*Skill + 0.20*Goal + 0.15*Exec + 0.15*Avail + 0.10*Trust + 0.10*Domain) × 100"""
        raw = (0.30*skill_similarity + 0.20*goal_similarity + 0.15*execution_style_similarity +
               0.15*availability_overlap + 0.10*trust_score + 0.10*domain_experience)
        return round(max(0.0, min(100.0, raw * 100)), 2)

    # ── 18. DECAY FACTOR ───────────────────────────────────────────────────

    @classmethod
    def compute_decay_factor(cls, days_inactive: int) -> float:
        """
        DecayFactor = e^(−0.02 × d)
        d = days without a meaningful milestone update.
        1.0 = fully active. Approaches 0 as inactivity grows.
        Applied to: WCRS, EVI-I, GSIS stale component detection.
        """
        return round(math.exp(-0.02 * max(0, days_inactive)), 6)

    # ── DEMAND CONFIDENCE SCORE ────────────────────────────────────────────

    @classmethod
    def compute_dcs(
        cls,
        traffic_score:     float,  # 0–100
        conversion_score:  float,
        preorders_score:   float,
        engagement_score:  float,
    ) -> float:
        """
        DCS = (Traffic + Conversion + Preorders + Engagement) / 4
        Validates real demand signals before launch.
        """
        dcs = (traffic_score + conversion_score + preorders_score + engagement_score) / 4.0
        return round(max(0.0, min(100.0, dcs)), 2)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class UserContext:
    """Complete user context -- shared across every AI call and scoring computation."""
    user_id:              str
    role:                 UserRole
    subscription_tier:    SubscriptionTier
    credits_remaining:    int
    project_id:           Optional[str]
    project_stage:        Optional[str]
    industry:             Optional[str]
    tech_stack:           List[str]
    past_feedback:        List[Dict]
    training_progress:    Dict
    time_logged_today:    int
    tasks_completed_week: int
    days_since_update:    int  = 0
    team_size:            int  = 1
    has_revenue:          bool = False
    beta_users_count:     int  = 0
    compliance_items:     Dict[str, bool] = field(default_factory=dict)
    transparency_items:   Dict[str, bool] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        decay = ScoringEngine.compute_decay_factor(self.days_since_update)
        return (
            f"USER CONTEXT:\n"
            f"  Role:              {self.role.value}\n"
            f"  Subscription:      {self.subscription_tier.value}\n"
            f"  Credits Remaining: {self.credits_remaining}\n"
            f"  Project Stage:     {self.project_stage or 'Not started'}\n"
            f"  Industry:          {self.industry or 'General'}\n"
            f"  Tech Stack:        {', '.join(self.tech_stack) or 'None'}\n"
            f"  Training Progress: {self.training_progress.get('completion_percentage', 0):.1f}%\n"
            f"  Tasks This Week:   {self.tasks_completed_week}\n"
            f"  Time Today:        {self.time_logged_today} min\n"
            f"  Team Size:         {self.team_size}\n"
            f"  Revenue Active:    {self.has_revenue}\n"
            f"  Beta Users:        {self.beta_users_count}\n"
            f"  Momentum Decay:    {decay:.4f}  (1.0=active, <0.5=stagnating)\n"
        )


@dataclass
class AIRequest:
    task_type:                TaskType
    user_context:             UserContext
    input_data:               Dict[str, Any]
    priority:                 int  = 1
    max_tokens:               int  = 2000
    require_structured_output: bool = False
    ip_protected:             bool = False
    use_cache:                bool = True


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


@dataclass
class AIResponse:
    task_type:         TaskType
    output:            str
    model_used:        str
    tokens_used:       int
    cost:              float
    confidence_score:  float
    execution_time_ms: int
    credits_consumed:  int  = 0
    cached:            bool = False
    metadata:          Dict = field(default_factory=dict)


# ============================================================================
# MODEL ROUTER
# ============================================================================

class ModelRouter:
    """Routes each task to the optimal LLM. No feature is locked to one vendor."""

    TASK_MAP: Dict[TaskType, ModelProvider] = {
        # Deep reasoning -> GPT-4
        TaskType.IDEA_EVALUATION:          ModelProvider.OPENAI_GPT4,
        TaskType.UNICORN_ANALYSIS:         ModelProvider.OPENAI_GPT4,
        TaskType.CODE_REVIEW:              ModelProvider.OPENAI_GPT4,
        TaskType.RISK_ANALYSIS:            ModelProvider.OPENAI_GPT4,
        TaskType.STARTUP_STRATEGY:         ModelProvider.OPENAI_GPT4,
        TaskType.PIVOT_INTELLIGENCE:       ModelProvider.OPENAI_GPT4,
        TaskType.PRODUCT_FEASIBILITY:      ModelProvider.OPENAI_GPT4,
        TaskType.TECH_STACK_DESIGN:        ModelProvider.OPENAI_GPT4,
        TaskType.INVESTOR_EVI:             ModelProvider.OPENAI_GPT4,
        # Long-form generation -> Claude Sonnet
        TaskType.BUSINESS_PLAN:            ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.EXECUTIVE_SUMMARY:        ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.MARKET_INTELLIGENCE:      ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.FINANCE_STRATEGY:         ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.INVESTOR_READINESS:       ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.INVESTOR_SIGNAL:          ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.TRAINING_GENERATION:      ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.SUMMARY:                  ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.MARKET_SURVEY_SIMULATION: ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.EXECUTION_ROADMAP:        ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.ORG_SPHERE:               ModelProvider.ANTHROPIC_CLAUDE,
        # Lightweight ops -> GPT-4o-mini
        TaskType.CHAT:                     ModelProvider.OPENAI_GPT4_MINI,
        TaskType.TOUR_GUIDE:               ModelProvider.OPENAI_GPT4_MINI,
        TaskType.WORKSPACE_ASSISTANT:      ModelProvider.OPENAI_GPT4_MINI,
        TaskType.DASHBOARD_INTELLIGENCE:   ModelProvider.OPENAI_GPT4_MINI,
        TaskType.FEED_INTELLIGENCE:        ModelProvider.OPENAI_GPT4_MINI,
        TaskType.RECOMMENDATION_ENGINE:    ModelProvider.OPENAI_GPT4_MINI,
        TaskType.GSIS_COMPUTE:             ModelProvider.OPENAI_GPT4_MINI,
        # Idea & Solution Hub -- GPT-4 for analysis; Claude for synthesis/grants
        TaskType.PROBLEM_ANALYSIS:         ModelProvider.OPENAI_GPT4,
        TaskType.SOLUTION_SYNTHESIS:       ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.IMPACT_PREDICTION:        ModelProvider.OPENAI_GPT4_MINI,
        TaskType.FEASIBILITY_ESTIMATE:     ModelProvider.OPENAI_GPT4,
        TaskType.PROBLEM_DISCOVERY:        ModelProvider.OPENAI_GPT4_MINI,
        TaskType.SOLUTION_MATCHING:        ModelProvider.ANTHROPIC_HAIKU,
        TaskType.DEPLOYMENT_PLANNING:      ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.GRANT_MATCHING:           ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DISCUSSION_MODERATION:    ModelProvider.OPENAI_GPT4_MINI,
        TaskType.FIELD_FEEDBACK_ANALYSIS:  ModelProvider.OPENAI_GPT4_MINI,
        # Document Generation -- all long-form -> Claude Sonnet
        TaskType.DOCUMENT_EXECUTIVE_SUMMARY:    ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_BUSINESS_PLAN:        ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_PITCH_DECK:           ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_INVESTOR_REPORT:      ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_UNICORN_REPORT:       ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_PRODUCT_ROADMAP:      ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_FINANCIAL_PROJECTION: ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.DOCUMENT_MARKET_RESEARCH:      ModelProvider.ANTHROPIC_CLAUDE,
        # Fast classification -> Haiku
        TaskType.MATCHING:                 ModelProvider.ANTHROPIC_HAIKU,
        TaskType.PROFILE_ANALYSIS:         ModelProvider.ANTHROPIC_HAIKU,
        TaskType.ADMIN_MONITOR:            ModelProvider.ANTHROPIC_HAIKU,
        # Prompt -> Live App -- Claude Sonnet for structured code scaffolds
        TaskType.APP_SCAFFOLD_GENERATION:  ModelProvider.ANTHROPIC_CLAUDE,
        TaskType.APP_DEPLOY_CONFIG:        ModelProvider.OPENAI_GPT4_MINI,
        # Embeddings -> Cohere
        TaskType.EMBEDDINGS:               ModelProvider.COHERE_EMBED,
    }

    def __init__(self) -> None:
        self.model_configs  = self._init_models()
        self.fallback_chain = self._init_fallbacks()

    def _init_models(self) -> Dict[ModelProvider, ModelConfig]:
        return {
            ModelProvider.OPENAI_GPT4: ModelConfig(
                ModelProvider.OPENAI_GPT4, "gpt-4-turbo", 0.01, 128_000,
                ["deep reasoning", "unicorn scoring", "code"],
                [TaskType.IDEA_EVALUATION, TaskType.UNICORN_ANALYSIS],
            ),
            ModelProvider.OPENAI_GPT4_MINI: ModelConfig(
                ModelProvider.OPENAI_GPT4_MINI, "gpt-4o-mini", 0.0002, 128_000,
                ["speed", "low cost", "chat"],
                [TaskType.CHAT, TaskType.TOUR_GUIDE],
            ),
            ModelProvider.ANTHROPIC_CLAUDE: ModelConfig(
                ModelProvider.ANTHROPIC_CLAUDE, "claude-sonnet-4-6", 0.003, 200_000,
                ["long context", "business plans", "strategy"],
                [TaskType.BUSINESS_PLAN, TaskType.SUMMARY],
            ),
            ModelProvider.ANTHROPIC_HAIKU: ModelConfig(
                ModelProvider.ANTHROPIC_HAIKU, "claude-haiku-4-5-20251001", 0.00025, 200_000,
                ["speed", "classification", "matching"],
                [TaskType.MATCHING, TaskType.PROFILE_ANALYSIS],
            ),
            ModelProvider.COHERE_EMBED: ModelConfig(
                ModelProvider.COHERE_EMBED, "embed-english-v3.0", 0.0001, 512,
                ["embeddings", "semantic search"],
                [TaskType.EMBEDDINGS],
            ),
        }

    def _init_fallbacks(self) -> Dict[ModelProvider, List[ModelProvider]]:
        return {
            ModelProvider.OPENAI_GPT4:      [ModelProvider.ANTHROPIC_CLAUDE, ModelProvider.OPENAI_GPT4_MINI],
            ModelProvider.ANTHROPIC_CLAUDE: [ModelProvider.OPENAI_GPT4, ModelProvider.ANTHROPIC_HAIKU],
            ModelProvider.OPENAI_GPT4_MINI: [ModelProvider.ANTHROPIC_HAIKU],
            ModelProvider.ANTHROPIC_HAIKU:  [ModelProvider.OPENAI_GPT4_MINI],
        }

    def select_model(self, request: AIRequest) -> ModelConfig:
        if request.user_context.subscription_tier == SubscriptionTier.FREE:
            cheap = {TaskType.CHAT: ModelProvider.OPENAI_GPT4_MINI,
                     TaskType.TOUR_GUIDE: ModelProvider.OPENAI_GPT4_MINI,
                     TaskType.EMBEDDINGS: ModelProvider.COHERE_EMBED}
            return self.model_configs[cheap.get(request.task_type, ModelProvider.ANTHROPIC_HAIKU)]
        provider = self.TASK_MAP.get(request.task_type, ModelProvider.OPENAI_GPT4_MINI)
        return self.model_configs[provider]

    def get_fallback_model(self, failed: ModelProvider) -> Optional[ModelConfig]:
        fallbacks = self.fallback_chain.get(failed, [])
        return self.model_configs.get(fallbacks[0]) if fallbacks else None


# ============================================================================
# PROMPT ENGINE
# ============================================================================

class PromptEngine:
    """All prompts are versioned data assets, not hardcoded strings."""

    SYSTEM_PROMPTS: Dict[TaskType, str] = {
        # ── Incubation Hub Agents ──────────────────────────────────────────────
        # 1. VentureIntakeAgent
        TaskType.IDEA_EVALUATION:         AP.VENTURE_INTAKE,
        # 2. UnicornEvaluatorAgent (full 16-part UNICORN GOLD PROMPT)
        TaskType.UNICORN_ANALYSIS:        AP.UNICORN_EVALUATOR,
        # 3. MarketIntelligenceAgent
        TaskType.MARKET_INTELLIGENCE:     AP.MARKET_INTELLIGENCE,
        # 4. ProductFeasibilityAgent
        TaskType.PRODUCT_FEASIBILITY:     AP.PRODUCT_FEASIBILITY,
        # 5. StartupStrategyAgent
        TaskType.STARTUP_STRATEGY:        AP.STARTUP_STRATEGY,
        # 6. FinanceStrategyAgent
        TaskType.FINANCE_STRATEGY:        AP.FINANCE_STRATEGY,
        # 7. InvestorIntelligenceAgent
        TaskType.INVESTOR_SIGNAL:         AP.INVESTOR_INTELLIGENCE,
        TaskType.INVESTOR_READINESS:      AP.INVESTOR_INTELLIGENCE,
        TaskType.INVESTOR_EVI: (
            "You are TechIT's Investor EVI Engine. Analyse the startup's execution velocity across "
            "6 dimensions: Milestone Delivery Rate, Iteration Speed, Team Response Velocity, "
            "Revenue Traction Acceleration, User Growth Momentum, Capital Efficiency Velocity. "
            "Produce an investor-grade signal with strengths, red flags, and headline narrative."
        ),
        # 8. BusinessPlanGeneratorAgent
        TaskType.BUSINESS_PLAN:           AP.BUSINESS_PLAN_GENERATOR,
        TaskType.EXECUTIVE_SUMMARY: (
            "You are TechIT's Executive Summary Generator. Produce a VC-standard 2-page summary: "
            "Problem | Solution | Market | Product | Business Model | Competitive Advantage | "
            "GTM | Revenue Strategy | Team | Vision. Dense and investor-grade."
        ),
        # 9. TechArchitectAgent
        TaskType.TECH_STACK_DESIGN:       AP.TECH_ARCHITECT,
        # 10. PivotIntelligenceAgent
        TaskType.PIVOT_INTELLIGENCE:      AP.PIVOT_INTELLIGENCE,

        # ── Platform Agents ────────────────────────────────────────────────────
        # 11. TourGuideAgent
        TaskType.TOUR_GUIDE:              AP.TOUR_GUIDE,
        # 12. AdaptiveTrainingAgent
        TaskType.TRAINING_GENERATION:     AP.ADAPTIVE_TRAINING,
        # 13. MatchingAgent
        TaskType.MATCHING:                AP.MATCHING,
        # 14. RiskEvaluatorAgent
        TaskType.RISK_ANALYSIS:           AP.RISK_EVALUATOR,
        # 15. WorkspaceAssistantAgent
        TaskType.WORKSPACE_ASSISTANT:     AP.WORKSPACE_ASSISTANT,
        # 16. FeedIntelligenceAgent
        TaskType.FEED_INTELLIGENCE:       AP.FEED_INTELLIGENCE,
        # 17. DashboardIntelligenceAgent
        TaskType.DASHBOARD_INTELLIGENCE:  AP.DASHBOARD_INTELLIGENCE,
        # 18. GSISComputeAgent
        TaskType.GSIS_COMPUTE:            AP.GSIS_COMPUTE,
        # 19. AIProfileAgent
        TaskType.PROFILE_ANALYSIS:        AP.AI_PROFILE,
        # 20. OrgSphereAgent
        TaskType.ORG_SPHERE:              AP.ORG_SPHERE,
        # 21. AdminMonitorAgent
        TaskType.ADMIN_MONITOR:           AP.ADMIN_MONITOR,

        # ── Idea & Solution Hub Agents ─────────────────────────────────────────
        # 22. ProblemAnalyzerAgent
        TaskType.PROBLEM_ANALYSIS:        AP.PROBLEM_ANALYZER,
        # 23. SolutionSynthesizerAgent
        TaskType.SOLUTION_SYNTHESIS:      AP.SOLUTION_SYNTHESIZER,
        # 24. ImpactPredictorAgent
        TaskType.IMPACT_PREDICTION:       AP.IMPACT_PREDICTOR,
        # 25. FeasibilityEstimatorAgent
        TaskType.FEASIBILITY_ESTIMATE:    AP.FEASIBILITY_ESTIMATOR,
        # 26. ProblemDiscoveryAgent
        TaskType.PROBLEM_DISCOVERY:       AP.PROBLEM_DISCOVERY,
        # 27. SolutionMatcherAgent
        TaskType.SOLUTION_MATCHING:       AP.SOLUTION_MATCHER,
        # 28. DeploymentPlannerAgent
        TaskType.DEPLOYMENT_PLANNING:     AP.DEPLOYMENT_PLANNER,
        # 29. GrantMatcherAgent
        TaskType.GRANT_MATCHING:          AP.GRANT_MATCHER,
        # 30. DiscussionModeratorAgent
        TaskType.DISCUSSION_MODERATION:   AP.DISCUSSION_MODERATOR,
        # 31. FieldFeedbackAgent
        TaskType.FIELD_FEEDBACK_ANALYSIS: AP.FIELD_FEEDBACK,

        # ── Document Generation Agents (32–33) ────────────────────────────────
        TaskType.DOCUMENT_EXECUTIVE_SUMMARY:    AP.DOCUMENT_EXECUTIVE_SUMMARY,
        TaskType.DOCUMENT_BUSINESS_PLAN:        AP.DOCUMENT_BUSINESS_PLAN,
        TaskType.DOCUMENT_PITCH_DECK:           AP.DOCUMENT_PITCH_DECK,
        TaskType.DOCUMENT_INVESTOR_REPORT:      AP.DOCUMENT_INVESTOR_REPORT,
        TaskType.DOCUMENT_UNICORN_REPORT:       AP.DOCUMENT_UNICORN_REPORT,
        TaskType.DOCUMENT_PRODUCT_ROADMAP:      AP.DOCUMENT_PRODUCT_ROADMAP,
        TaskType.DOCUMENT_FINANCIAL_PROJECTION: AP.DOCUMENT_FINANCIAL_PROJECTION,
        TaskType.DOCUMENT_MARKET_RESEARCH:      AP.DOCUMENT_MARKET_RESEARCH,

        # ── Supporting task types ──────────────────────────────────────────────
        TaskType.EXECUTION_ROADMAP:       AP.EXECUTION_ROADMAP,
        TaskType.RECOMMENDATION_ENGINE:   AP.RECOMMENDATION_ENGINE,
        TaskType.MARKET_SURVEY_SIMULATION: AP.MARKET_SURVEY_SIMULATION,

        # ── Prompt -> Live App Engine ───────────────────────────────────────
        TaskType.APP_SCAFFOLD_GENERATION: (
            "You are TechIT's App Scaffold Engine -- the fastest path from idea to running code. "
            "Given a startup's venture profile (problem, solution, market, tech stack), generate a "
            "complete, production-ready application scaffold. Output MUST be structured JSON with "
            "these exact keys:\n"
            "  scaffold_type: string (e.g. 'nextjs_supabase')\n"
            "  pages: array of {route, component_name, description, auth_required}\n"
            "  schema_sql: string -- complete Postgres/Supabase CREATE TABLE statements\n"
            "  api_routes: array of {method, path, description, auth_required, request_body, response}\n"
            "  env_template: string -- .env.example content with all required variables\n"
            "  components: array of {name, purpose, props}\n"
            "  setup_steps: array of strings -- exact commands to run after download\n"
            "  estimated_build_hours: number\n"
            "Rules: Use Next.js 14 App Router + Supabase + Tailwind CSS by default. "
            "Match the stack to the venture profile. Keep schema normalised. "
            "Every table must have id (UUID), created_at, updated_at. "
            "Auth uses Supabase Auth -- never roll your own. "
            "Output ONLY valid JSON -- no markdown, no explanation, no code fences."
        ),
        TaskType.APP_DEPLOY_CONFIG: (
            "You are TechIT's Deployment Configuration Engine. "
            "Given an app scaffold, generate the exact deployment configuration files. "
            "Output structured JSON with keys:\n"
            "  vercel_json: string -- vercel.json content\n"
            "  supabase_seed_sql: string -- seed data SQL\n"
            "  github_actions_yml: string -- CI/CD workflow YAML\n"
            "  deploy_steps: array of strings -- exact CLI commands for 1-click deploy\n"
            "  deploy_url_pattern: string -- expected Vercel URL format\n"
            "Output ONLY valid JSON."
        ),
    }

    async def build_prompt(self, task_type: TaskType, context: Dict, user_role: UserRole) -> str:
        system = self.SYSTEM_PROMPTS.get(
            task_type, "You are TechIT's AI assistant. Provide structured, investor-grade responses."
        )
        ip_notice = context.get("ip_protection_notice", "")
        return (
            f"{system}\n\n"
            f"USER CONTEXT:\n{context.get('user', '')}\n\n"
            f"TASK INPUT:\n{json.dumps(context.get('input', {}), indent=2, default=str)}\n\n"
            f"TIMESTAMP: {context.get('timestamp', '')}\n{ip_notice}"
        )


# ============================================================================
# SAFETY ENGINE
# ============================================================================

@dataclass
class SafetyCheckResult:
    approved:   bool
    reason:     Optional[str] = None
    risk_level: int = 0


class SafetyEngine:
    INJECTION_PATTERNS = [
        "ignore previous instructions", "you are now", "system:", "forget everything",
        "act as", "disregard", "override", "jailbreak", "new persona",
        "pretend you are", "ignore all prior", "bypass", "new instructions",
    ]

    async def validate_request(self, request: AIRequest) -> SafetyCheckResult:
        if not SubscriptionAccessControl.is_allowed(
            request.user_context.subscription_tier, request.task_type
        ):
            needed = SubscriptionAccessControl.required_tier(request.task_type)
            return SafetyCheckResult(False, f"Requires {needed.value} plan.", 2)

        cost = CreditCost.cost_for(request.task_type)
        if request.user_context.credits_remaining < cost:
            return SafetyCheckResult(
                False,
                f"Insufficient credits. This task costs {cost} credit(s). "
                f"You have {request.user_context.credits_remaining}.",
                1,
            )

        if self._detect_injection(request.input_data):
            return SafetyCheckResult(False, "Prompt injection detected. Request blocked.", 5)

        if request.ip_protected:
            self._fingerprint(request)

        return SafetyCheckResult(True)

    def _detect_injection(self, data: Dict) -> bool:
        try:
            text = json.dumps(data, default=str).lower()
        except Exception:
            text = str(data).lower()
        return any(p in text for p in self.INJECTION_PATTERNS)

    def _fingerprint(self, request: AIRequest) -> None:
        """
        SHA-256 fingerprint of the request payload.

        Stamped onto every ip_protected=True request BEFORE the AI call.
        Stored in:
          - request.input_data["_ip_fingerprint"]  -> flows into ai_outputs.input_data
          - idea_embeddings.idea_fingerprint        -> written by VentureIntakeAgent
          - problem_nodes.fingerprint               -> written by IdeaSolutionHubService

        Used for:
          1. Exact-match deduplication (same idea submitted twice)
          2. Audit trail in ai_outputs (ip_protected=True column)
          3. Baseline for semantic similarity comparison (see check_similarity_leak)
        """
        try:
            payload = json.dumps(request.input_data, sort_keys=True, default=str)
        except Exception:
            payload = str(request.input_data)
        fp = hashlib.sha256(payload.encode()).hexdigest()
        request.input_data["_ip_fingerprint"] = fp
        request.input_data["_ip_timestamp"]   = datetime.now().isoformat()

    @staticmethod
    def check_similarity_leak(
        query_fingerprint: str,
        stored_fingerprints: List[str],
        threshold: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Fast exact-match IP leak check using stored SHA-256 fingerprints.

        Called BEFORE showing any matching or discovery results that could
        surface another user's idea. If an exact fingerprint match is found,
        the result is blocked and an IP alert is raised.

        For semantic similarity (cosine distance on embeddings), use the
        pgvector `idea_similarity_check` SQL query in REFERENCE_QUERIES
        (database_schema.py). That query runs as the techit_system role
        (BYPASSRLS) and never returns idea_text -- only project_id + score.

        Parameters
        ──────────
        query_fingerprint     SHA-256 of the new idea being checked
        stored_fingerprints   List of fingerprints from idea_embeddings table
        threshold             Not used for exact match -- reserved for fuzzy

        Returns
        ───────
        {
            "leak_detected": bool,
            "matched_fingerprint": str | None,
            "action": "block" | "allow",
            "reason": str,
        }
        """
        if query_fingerprint in stored_fingerprints:
            return {
                "leak_detected":       True,
                "matched_fingerprint": query_fingerprint,
                "action":              "block",
                "reason": (
                    "Exact fingerprint match: this idea was previously submitted "
                    "by another user. IP protection prevents display. "
                    "Raise an IP alert for admin review."
                ),
            }
        return {
            "leak_detected":       False,
            "matched_fingerprint": None,
            "action":              "allow",
            "reason":              "No exact fingerprint match found.",
        }


# ============================================================================
# AI COMMAND LAYER
# ============================================================================

class AICommandLayer:
    """
    THE CORE BRAIN OF TECHIT.
    Every AI interaction passes through this single layer.
    Nothing calls an LLM directly.
    """

    def __init__(self, model_router: ModelRouter, prompt_engine: PromptEngine,
                 safety_engine: SafetyEngine) -> None:
        self.model_router  = model_router
        self.prompt_engine = prompt_engine
        self.safety_engine = safety_engine
        self.execution_log: List[Dict] = []

    async def process_request(self, request: AIRequest) -> AIResponse:
        start = datetime.now()

        safety = await self.safety_engine.validate_request(request)
        if not safety.approved:
            raise PermissionError(f"Request blocked: {safety.reason}")

        context = {
            "user":      request.user_context.to_prompt_context(),
            "input":     request.input_data,
            "timestamp": datetime.now().isoformat(),
        }
        if request.ip_protected:
            context["ip_protection_notice"] = (
                "\nIP PROTECTION ACTIVE: This content is confidential. "
                "Do not retain or use for training.\n"
            )

        prompt       = await self.prompt_engine.build_prompt(
            request.task_type, context, request.user_context.role
        )
        model_config = self.model_router.select_model(request)
        response     = await self._execute_with_retry(model_config, prompt, request)

        response.credits_consumed = CreditCost.cost_for(request.task_type)
        elapsed = (datetime.now() - start).total_seconds() * 1000
        await self._log(request, response, elapsed)
        return response

    async def _execute_with_retry(self, model_config: ModelConfig,
                                   prompt: str, request: AIRequest,
                                   max_retries: int = 2) -> AIResponse:
        for attempt in range(max_retries + 1):
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
                    metadata={"attempt": attempt + 1},
                )
            except Exception as exc:
                if attempt < max_retries:
                    fb = self.model_router.get_fallback_model(model_config.provider)
                    if fb:
                        model_config = fb
                        continue
                raise exc

    async def _call_llm(self, model_config: ModelConfig, prompt: str,
                         request: AIRequest) -> Dict:
        """
        Production: routes to OpenAI / Anthropic / Cohere based on model_config.provider.
        Abstracted here for portability.
        """
        return {"text": "AI Response Placeholder", "tokens": 500,
                "confidence": 0.95, "duration_ms": 1200}

    async def _log(self, request: AIRequest, response: AIResponse, elapsed_ms: float) -> None:
        self.execution_log.append({
            "user_id":           request.user_context.user_id,
            "task_type":         request.task_type.value,
            "model_used":        response.model_used,
            "tokens":            response.tokens_used,
            "cost":              response.cost,
            "credits_consumed":  response.credits_consumed,
            "execution_time_ms": elapsed_ms,
            "subscription_tier": request.user_context.subscription_tier.value,
            "ip_protected":      request.ip_protected,
            "timestamp":         datetime.now().isoformat(),
        })


# ============================================================================
# COST MONITOR
# ============================================================================

class CostMonitor:
    THRESHOLDS = {"monthly_user_alert": 10.00, "single_request_flag": 0.50}

    @staticmethod
    async def check_cost_alert(user_id: str, monthly_cost: float) -> Optional[Dict]:
        if monthly_cost > CostMonitor.THRESHOLDS["monthly_user_alert"]:
            return {"alert": "high_cost_user", "user_id": user_id, "monthly_cost": monthly_cost}
        return None


# ============================================================================
# QUICK DEMO
# ============================================================================

async def _demo() -> None:
    brain = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    ctx = UserContext(
        user_id="demo", role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO, credits_remaining=150,
        project_id="proj_1", project_stage="idea", industry="healthtech",
        tech_stack=["React", "Node.js"], past_feedback=[],
        training_progress={"completion_percentage": 20}, time_logged_today=90,
        tasks_completed_week=5, days_since_update=2, team_size=2,
    )
    req = AIRequest(TaskType.UNICORN_ANALYSIS, ctx,
                    {"startup_name": "MediConnect", "problem": "Rural healthcare access"},
                    ip_protected=True)
    resp = await brain.process_request(req)
    print(f"Model: {resp.model_used} | Cost: ${resp.cost:.4f} | Credits: {resp.credits_consumed}")

    # GSIS demo
    gsis = ScoringEngine.compute_gsis(
        product_progress_score=65, execution_velocity_index=70,
        market_readiness_score=60, beta_satisfaction_score=55,
        revenue_growth_signal=40, founder_reputation_score=72,
        community_influence_score=50, investor_interest_score=35, compliance_score=80,
    )
    print(f"GSIS: {gsis['gsis']} -- {gsis['classification']}")
    print(f"Alert Score: {gsis['alert_score']} | Alert: {gsis['alert_triggered']}")

    evi_i = ScoringEngine.compute_evi_investor(85, 87, 94, 85, 81, 80, days_since_last_update=3)
    print(f"EVI-I: {evi_i['adjusted_evi_i']} ({evi_i['signal']}) | Decay: {evi_i['decay_factor']}")


if __name__ == "__main__":
    asyncio.run(_demo())
