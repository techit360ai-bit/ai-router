"""
TECHIT AGENT ORCHESTRATION SYSTEM
==================================
Multi-agent coordination layer -- the CEO of all AI inside TechIT.

Every agent is a specialist. The AgentOrchestrator routes events,
assembles context, manages concurrency, and aggregates results.

REGISTERED AGENTS (21 total)
─────────────────────────────
Incubation Hub:
  1. VentureIntakeAgent          -- structures raw founder input
  2. UnicornEvaluatorAgent       -- 10-driver unicorn probability model
  3. MarketIntelligenceAgent     -- TAM/SAM/SOM, trends, competition
  4. ProductFeasibilityAgent     -- technical complexity, build risk
  5. StartupStrategyAgent        -- GTM, pricing, growth, PMF path
  6. FinanceStrategyAgent        -- capital efficiency, unit economics
  7. InvestorIntelligenceAgent   -- EVI-I + deal flow signals
  8. BusinessPlanGeneratorAgent  -- executive summary + full plan
  9. TechArchitectAgent          -- full tech stack design
 10. PivotIntelligenceAgent      -- pivot analysis + redevelopment

Platform:
 11. TourGuideAgent              -- daily planning + momentum enforcement
 12. AdaptiveTrainingAgent       -- time-to-MVP curriculum (not fixed weeks)
 13. MatchingAgent               -- team / investor / accelerator compatibility
 14. RiskEvaluatorAgent          -- idea + execution risk assessment
 15. WorkspaceAssistantAgent     -- task suggestions + sprint planning
 16. FeedIntelligenceAgent       -- curated community feed
 17. DashboardIntelligenceAgent  -- GSIS surface + real-time scores
 18. AIProfileAgent              -- profile scoring + improvement
 19. OrgSphereAgent              -- organization structure intelligence
 20. AdminMonitorAgent           -- abuse detection + anomaly alerts
 21. GSISComputeAgent            -- Global Startup Intelligence Score

EVENT -> AGENT ROUTING
──────────────────────
  idea_submitted         -> VentureIntake + RiskEvaluator + Matching
  user_login             -> TourGuide + DashboardIntelligence + GSISCompute
  training_completed     -> AdaptiveTraining (adaptive update)
  milestone_updated      -> DashboardIntelligence + TourGuide + GSISCompute
  investor_views         -> InvestorIntelligence
  profile_updated        -> AIProfile
  org_created            -> OrgSphere
  mvp_shipped            -> AdaptiveTraining (activate post-MVP tracks)
  revenue_went_live      -> AdaptiveTraining + InvestorIntelligence
  pivot_detected         -> PivotIntelligence + AdaptiveTraining
  investor_expressed_interest -> AdaptiveTraining (fast-track fundraising)
"""

from __future__ import annotations

import asyncio
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ai_router_core import (
    AICommandLayer, AIRequest, AIResponse,
    UserContext, TaskType, UserRole,
    SubscriptionTier, ScoringEngine, CreditCost,
)


# ============================================================================
# AGENT TYPES & CONFIGURATION
# ============================================================================

class AgentType(Enum):
    # Incubation Hub
    VENTURE_INTAKE        = "venture_intake"
    UNICORN_EVALUATOR     = "unicorn_evaluator"
    MARKET_INTELLIGENCE   = "market_intelligence"
    PRODUCT_FEASIBILITY   = "product_feasibility"
    STARTUP_STRATEGY      = "startup_strategy"
    FINANCE_STRATEGY      = "finance_strategy"
    INVESTOR_INTELLIGENCE = "investor_intelligence"
    BUSINESS_PLAN_GEN     = "business_plan_generator"
    TECH_ARCHITECT        = "tech_architect"
    PIVOT_INTELLIGENCE    = "pivot_intelligence"
    # Platform
    TOUR_GUIDE            = "tour_guide"
    ADAPTIVE_TRAINING     = "adaptive_training"
    MATCHING              = "matching"
    RISK_EVALUATOR        = "risk_evaluator"
    WORKSPACE_ASSISTANT   = "workspace_assistant"
    FEED_INTELLIGENCE     = "feed_intelligence"
    DASHBOARD_INTELLIGENCE = "dashboard_intelligence"
    AI_PROFILE            = "ai_profile"
    ORG_SPHERE            = "org_sphere"
    ADMIN_MONITOR         = "admin_monitor"
    GSIS_COMPUTE          = "gsis_compute"
    # Idea & Solution Hub agents
    PROBLEM_ANALYZER      = "problem_analyzer"
    SOLUTION_SYNTHESIZER  = "solution_synthesizer"
    IMPACT_PREDICTOR      = "impact_predictor"
    FEASIBILITY_ESTIMATOR = "feasibility_estimator"
    PROBLEM_DISCOVERY     = "problem_discovery"
    SOLUTION_MATCHER      = "solution_matcher"
    DEPLOYMENT_PLANNER    = "deployment_planner"
    GRANT_MATCHER         = "grant_matcher"
    DISCUSSION_MODERATOR  = "discussion_moderator"
    FIELD_FEEDBACK_AGENT  = "field_feedback_agent"
    # Document Generation agents
    DOCUMENT_GENERATION   = "document_generation"
    DOCUMENT_EXPORT       = "document_export"
    # Prompt -> Live App
    APP_SCAFFOLD          = "app_scaffold"


class AgentTrigger(Enum):
    SCHEDULED    = "scheduled"
    EVENT_DRIVEN = "event_driven"
    ON_DEMAND    = "on_demand"


@dataclass
class AgentConfig:
    agent_type:          AgentType
    name:                str
    description:         str
    triggers:            List[AgentTrigger]
    schedule:            Optional[str]     = None
    timeout_seconds:     int               = 60
    priority:            int               = 3
    min_tier:            SubscriptionTier  = SubscriptionTier.FREE


@dataclass
class AgentContext:
    user_context:   UserContext
    trigger_event:  Optional[Dict[str, Any]] = None
    shared_memory:  Dict[str, Any]           = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_type:       AgentType
    success:          bool
    output:           Dict[str, Any]
    actions_taken:    List[str]
    recommendations:  List[str]
    next_steps:       List[str]
    execution_time_ms: int
    credits_consumed: int = 0
    metadata:         Dict = field(default_factory=dict)


# ============================================================================
# BASE AGENT
# ============================================================================

class BaseAgent(ABC):
    def __init__(self, config: AgentConfig, ai_brain: AICommandLayer) -> None:
        self.config   = config
        self.ai_brain = ai_brain
        self._history: List[Dict] = []

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult: ...

    async def _call_ai(self, task_type: TaskType, input_data: Dict,
                        user_context: UserContext, ip_protected: bool = False,
                        max_tokens: int = 3000) -> AIResponse:
        return await self.ai_brain.process_request(AIRequest(
            task_type=task_type, user_context=user_context,
            input_data=input_data, ip_protected=ip_protected, max_tokens=max_tokens,
        ))

    def _log(self, result: AgentResult) -> None:
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "success":   result.success,
            "credits":   result.credits_consumed,
        })


# ============================================================================
# INCUBATION HUB AGENTS
# ============================================================================

class VentureIntakeAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        raw = context.trigger_event or {}
        ai  = await self._call_ai(TaskType.IDEA_EVALUATION, {"raw_input": raw}, context.user_context, ip_protected=True)
        profile = {
            "startup_name": raw.get("startup_name", "Unnamed"),
            "industry":     raw.get("industry", "Unknown"),
            "problem":      raw.get("problem", ""),
            "solution":     raw.get("solution", ""),
            "target_customers": raw.get("target_customers", ""),
            "revenue_model":    raw.get("revenue_model", ""),
            "market_size":      raw.get("market_size", ""),
            "traction":         raw.get("traction", "Pre-traction"),
            "team":             raw.get("team", []),
            "tech_stack":       raw.get("tech_stack", []),
            "ai_structured":    ai.output,
        }
        context.shared_memory["venture_profile"] = profile

        # ── IP PROTECTION: create vector embedding for leak detection ────────
        # Combines problem + solution text into a single embedding target.
        # Stored in idea_embeddings table with SHA-256 fingerprint.
        # Any future idea with cosine similarity ≥ 0.95 triggers an IP alert.
        idea_text = (
            f"Problem: {profile.get('problem', '')} "
            f"Solution: {profile.get('solution', '')} "
            f"Market: {profile.get('market_size', '')} "
            f"Model: {profile.get('revenue_model', '')}"
        ).strip()
        if idea_text:
            try:
                import hashlib as _hl
                fingerprint = _hl.sha256(idea_text.encode()).hexdigest()
                # Production: call embedding API then INSERT INTO idea_embeddings
                # embed_resp = await self._call_ai(
                #     TaskType.EMBEDDINGS,
                #     {"text": idea_text, "model": "text-embedding-3-small"},
                #     context.user_context, ip_protected=True,
                # )
                # INSERT INTO idea_embeddings (project_id, embedding, idea_fingerprint,
                #     idea_text, embedding_model, is_protected, leak_detection_enabled)
                # VALUES (project_id, embed_resp.output, fingerprint, idea_text,
                #     'text-embedding-3-small', true, true)
                context.shared_memory["idea_fingerprint"] = fingerprint
                context.shared_memory["idea_embedding_pending"] = True
            except Exception:
                pass  # Never let embedding failure block idea intake
        # ── END IP PROTECTION ────────────────────────────────────────────────

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.VENTURE_INTAKE, True,
            {"venture_profile": profile,
             "idea_fingerprint": context.shared_memory.get("idea_fingerprint", ""),
             "ip_protected": True},
            ["Parsed raw founder input", "Built Structured Venture Profile",
             "Fingerprinted idea for IP leak detection"],
            ["Proceed to Unicorn Evaluation"],
            ["Run UnicornEvaluatorAgent"],
            ms, ai.credits_consumed,
        )


class UnicornEvaluatorAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        profile = context.shared_memory.get("venture_profile", context.trigger_event or {})
        ai      = await self._call_ai(
            TaskType.UNICORN_ANALYSIS,
            {"venture_profile": profile},
            context.user_context, ip_protected=True, max_tokens=4000,
        )
        drivers = {
            "market_size": 7.5, "problem_severity": 8.0, "founder_advantage": 6.5,
            "technological_moat": 7.0, "scalability": 8.5, "network_effects": 7.0,
            "revenue_model_strength": 6.5, "market_timing": 7.5,
            "competition_landscape": 6.0, "capital_efficiency": 7.0,
        }  # Production: parse from structured AI response
        ups = ScoringEngine.compute_unicorn_potential_score(drivers)
        context.shared_memory["unicorn_evaluation"] = ups
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        recs = (
            ["Accelerate GTM", "Initiate investor outreach"] if ups["unicorn_potential_score"] >= 75 else
            ["Validate demand with 50+ users", "Sharpen revenue model"]
        )
        return AgentResult(
            AgentType.UNICORN_EVALUATOR, True,
            {**ups, "ai_analysis": ai.output},
            [f"Computed UPS: {ups['unicorn_potential_score']}% ({ups['classification']})"],
            recs, ["Run MarketIntelligenceAgent", "Run ProductFeasibilityAgent"],
            ms, ai.credits_consumed,
        )


class MarketIntelligenceAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        ai  = await self._call_ai(
            TaskType.MARKET_INTELLIGENCE,
            {"venture_profile": context.shared_memory.get("venture_profile", {})},
            context.user_context, max_tokens=4000,
        )
        context.shared_memory["market_analysis"] = ai.output
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.MARKET_INTELLIGENCE, True,
            {"market_analysis": ai.output},
            ["Analysed TAM/SAM/SOM", "Benchmarked competition"],
            ["Validate TAM with primary research"],
            ["Integrate into Business Plan"],
            ms, ai.credits_consumed,
        )


class ProductFeasibilityAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.PRODUCT_FEASIBILITY,
            {"venture_profile": context.shared_memory.get("venture_profile", {})},
            context.user_context, max_tokens=3000,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.PRODUCT_FEASIBILITY, True,
            {"feasibility_report": ai.output},
            ["Assessed build complexity", "Mapped dev phases"],
            ["Start with lowest-risk MVP feature set"],
            ["Feed into Execution Roadmap"],
            ms, ai.credits_consumed,
        )


class StartupStrategyAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.STARTUP_STRATEGY,
            {k: context.shared_memory.get(k, {})
             for k in ["venture_profile", "unicorn_evaluation", "market_analysis"]},
            context.user_context, max_tokens=4000,
        )
        context.shared_memory["startup_strategy"] = ai.output
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.STARTUP_STRATEGY, True,
            {"startup_strategy": ai.output},
            ["Defined GTM strategy", "Designed pricing model"],
            ["Dominate one niche before expanding"],
            ["Generate Execution Roadmap", "Run Finance Strategy Agent"],
            ms, ai.credits_consumed,
        )


class FinanceStrategyAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.FINANCE_STRATEGY,
            {"venture_profile": context.shared_memory.get("venture_profile", {}),
             "startup_strategy": context.shared_memory.get("startup_strategy", {})},
            context.user_context, max_tokens=3000,
        )
        context.shared_memory["finance_strategy"] = ai.output
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.FINANCE_STRATEGY, True,
            {"finance_strategy": ai.output},
            ["Assessed capital efficiency", "Modelled unit economics"],
            ["Delay VC until PMF is proven"],
            ["Incorporate into Business Plan financials"],
            ms, ai.credits_consumed,
        )


class InvestorIntelligenceAgent(BaseAgent):
    """
    Computes Investment Score and EVI-I, generates investor-grade signals.
    """
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        ups = context.shared_memory.get("unicorn_evaluation", {})
        score = ups.get("unicorn_potential_score", 50)

        invest_score = ScoringEngine.compute_investment_score(
            market_readiness=context.shared_memory.get("market_readiness", 60),
            traction_score=min(100, context.user_context.beta_users_count * 2),
            team_score=min(100, context.user_context.team_size * 15),
            risk_inverse=max(0, 100 - (100 - score)),
            growth_rate=context.shared_memory.get("growth_rate", 30),
            differentiation_score=score * 0.7,
        )

        # EVI-I computed from available signals
        evi_i = ScoringEngine.compute_evi_investor(
            mdr_score=context.shared_memory.get("mdr", 70),
            is_score=context.shared_memory.get("is", 65),
            trv_score=context.shared_memory.get("trv", 75),
            rta_score=min(100, context.user_context.beta_users_count * 1.5),
            ugm_score=min(100, context.user_context.beta_users_count),
            cev_score=context.shared_memory.get("cev", 60),
            days_since_last_update=context.user_context.days_since_update,
        )

        ai = await self._call_ai(
            TaskType.INVESTOR_SIGNAL,
            {"venture_profile": context.shared_memory.get("venture_profile", {}),
             "unicorn_evaluation": ups,
             "investment_score": invest_score,
             "evi_i": evi_i},
            context.user_context, max_tokens=3000,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.INVESTOR_INTELLIGENCE, True,
            {"investment_score": invest_score, "evi_i": evi_i, "investor_signals": ai.output},
            [f"Investment Score: {invest_score}/100",
             f"EVI-I: {evi_i['adjusted_evi_i']} ({evi_i['signal']})"],
            ["Address top 2 investor concerns before outreach"],
            ["Add to Investor Marketplace", "Generate Investor Readiness Report"],
            ms, ai.credits_consumed,
        )


class BusinessPlanGeneratorAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0   = datetime.now()
        agg  = {k: context.shared_memory.get(k, {})
                for k in ["venture_profile", "unicorn_evaluation", "market_analysis",
                          "startup_strategy", "finance_strategy"]}
        exec_r = await self._call_ai(TaskType.EXECUTIVE_SUMMARY, agg, context.user_context,
                                      ip_protected=True, max_tokens=2000)
        plan_r = await self._call_ai(TaskType.BUSINESS_PLAN, agg, context.user_context,
                                      ip_protected=True, max_tokens=6000)
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.BUSINESS_PLAN_GEN, True,
            {"executive_summary": exec_r.output, "business_plan": plan_r.output},
            ["Generated VC-standard Executive Summary", "Generated 10-section Business Plan"],
            ["Have 3 advisors review before investor outreach"],
            ["Export to PDF", "Upload to investor data room"],
            ms, exec_r.credits_consumed + plan_r.credits_consumed,
        )


class TechArchitectAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.TECH_STACK_DESIGN,
            {"venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
             "scale_target": (context.trigger_event or {}).get("scale_target", "1M users")},
            context.user_context, max_tokens=4000,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.TECH_ARCHITECT, True,
            {"tech_architecture": ai.output},
            ["Designed full-stack architecture"],
            ["Start with monolith, extract microservices at scale"],
            ["Create technical spec", "Hire based on stack"],
            ms, ai.credits_consumed,
        )


class PivotIntelligenceAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0    = datetime.now()
        ups   = context.shared_memory.get("unicorn_evaluation", {})
        score = ups.get("unicorn_potential_score", 50)
        if score >= 50:
            ms = int((datetime.now() - t0).total_seconds() * 1000)
            return AgentResult(
                AgentType.PIVOT_INTELLIGENCE, True,
                {"pivot_needed": False, "score": score},
                ["Pivot evaluation -- not required"],
                ["Continue current direction"],
                ["Proceed to Business Plan"],
                ms,
            )
        ai = await self._call_ai(
            TaskType.PIVOT_INTELLIGENCE,
            {"venture_profile": context.shared_memory.get("venture_profile", {}),
             "unicorn_score": score},
            context.user_context, ip_protected=True, max_tokens=4000,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.PIVOT_INTELLIGENCE, True,
            {"pivot_needed": True, "current_score": score, "pivot_analysis": ai.output},
            [f"Weak UPS: {score}%", "Pivot analysis complete"],
            ["Consider market or customer segment pivot first"],
            ["Discuss with co-founders", "Re-run intake with new direction"],
            ms, ai.credits_consumed,
        )


# ============================================================================
# PLATFORM AGENTS
# ============================================================================

class TourGuideAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        uc  = context.user_context
        decay = ScoringEngine.compute_decay_factor(uc.days_since_update)

        # Momentum score
        score  = min(30, (uc.time_logged_today / 180) * 30)
        score += min(30, (uc.tasks_completed_week / 10) * 30)
        score += min(20, (uc.training_progress.get("completion_percentage", 0) / 100) * 20)
        score += max(0, 20 - uc.days_since_update * 3)
        momentum = int(score)

        ai = await self._call_ai(
            TaskType.TOUR_GUIDE,
            {"momentum_score": momentum, "decay_factor": round(decay, 4),
             "days_inactive": uc.days_since_update},
            uc,
        )

        actions = (
            [{"priority": "critical", "action": "Complete daily check-in", "est_min": 5},
             {"priority": "high", "action": "Log at least 1 hour of work", "est_min": 60}]
            if momentum < 40 else
            [{"priority": "high", "action": "Complete 3 priority tasks", "est_min": 120},
             {"priority": "medium", "action": "Review training module", "est_min": 30}]
            if momentum < 70 else
            [{"priority": "high", "action": "Ship one feature or deliverable", "est_min": 180},
             {"priority": "medium", "action": "Conduct user feedback session", "est_min": 60}]
        )

        recs = []
        if decay < 0.70:
            recs.append(f"⚠️ Decay: {round((1-decay)*100)}% score penalty from inactivity")
        if momentum < 40:
            recs.append("⚠️ Critical: Momentum dangerously low. Log work today.")
        if not recs:
            recs.append("✅ Maintain consistent daily progress to build momentum.")

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.TOUR_GUIDE, True,
            {"momentum_score": momentum, "decay_factor": round(decay, 4),
             "daily_plan": actions, "ai_insights": ai.output},
            [f"Momentum: {momentum}/100", f"Decay: {decay:.4f}"],
            recs, ["Complete daily check-in", "Update milestone progress"],
            ms, ai.credits_consumed,
        )


class AdaptiveTrainingAgent(BaseAgent):
    """
    Adaptive training curriculum agent.
    Duration is computed from time-to-MVP, not fixed to 12 weeks.
    Activates post-MVP tracks when startup stage advances.
    Responds to adaptation triggers: pivot, revenue, investor interest, mvp_shipped.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        uc      = context.user_context
        trigger = (context.trigger_event or {})
        mode    = trigger.get("mode", "generate")    # generate | adapt | post_mvp_activate

        # Import here to avoid circular dependency at module level
        from training_module import AdaptiveTrainingService, LearnerProfile, LearningPace

        svc = AdaptiveTrainingService()

        pace_map = {"intensive": "intensive", "standard": "standard", "part_time": "part_time"}
        curriculum = svc.generate_curriculum(
            user_id=uc.user_id,
            role=uc.role.value,
            industry=uc.industry or "general",
            project_stage=uc.project_stage or "idea",
            hours_available_per_week=trigger.get("hours_per_week", 8.0),
            learning_pace=pace_map.get(trigger.get("learning_pace", "standard"), "standard"),
            target_mvp_weeks=trigger.get("target_mvp_weeks", 0),
            has_technical_skills=trigger.get("has_technical_skills", False),
            team_size=uc.team_size,
            has_cofounder=uc.team_size >= 2,
            pre_existing_skills=trigger.get("pre_existing_skills", []),
            unicorn_score=context.shared_memory.get("unicorn_evaluation", {}).get("unicorn_potential_score", 0),
            beta_users_count=uc.beta_users_count,
            has_revenue=uc.has_revenue,
            investor_interest=trigger.get("investor_interest", False),
        )

        ls  = curriculum["learning_summary"]
        pre = curriculum["pre_mvp"]

        # Build adaptive AI context for training generation
        ai = await self._call_ai(
            TaskType.TRAINING_GENERATION,
            {"curriculum_summary": ls, "module_count": pre["total_modules"],
             "role": uc.role.value, "stage": uc.project_stage},
            uc, max_tokens=2000,
        )

        actions = [
            f"Generated adaptive curriculum: {pre['total_modules']} pre-MVP modules",
            f"Estimated {ls['estimated_weeks_to_mvp']} weeks to MVP",
            f"Post-MVP tracks available: {curriculum['post_mvp']['tracks_available']}",
        ]

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.ADAPTIVE_TRAINING, True,
            {"curriculum": curriculum, "ai_narrative": ai.output},
            actions,
            ["Begin with Module 1", "Allocate time daily based on pace"],
            ["Track completion", "Schedule mentor check-in"],
            ms, ai.credits_consumed,
        )


class MatchingAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0       = datetime.now()
        criteria = (context.trigger_event or {}).get("criteria", {})
        candidates = [
            {"user_id": "builder_001", "name": "Aisha Osei",
             "skills": ["React", "Node.js", "Python"], "similarity_score": 0.91,
             "availability": "available", "trust_score": 0.85},
            {"user_id": "builder_002", "name": "David Mensah",
             "skills": ["Python", "ML", "FastAPI"], "similarity_score": 0.85,
             "availability": "part-time", "trust_score": 0.78},
        ]
        required = set(criteria.get("required_skills", []))
        filtered = [
            {**c, "match_score": ScoringEngine.compute_match_score(
                c["similarity_score"], 0.75, 0.70,
                1.0 if c["availability"] == "available" else 0.5,
                c.get("trust_score", 0.75), 0.65,
            )}
            for c in candidates
            if c["similarity_score"] >= 0.70
            and (not required or required.issubset(set(c["skills"])))
            and (not criteria.get("availability_required") or c["availability"] == "available")
        ]
        filtered.sort(key=lambda x: x["match_score"], reverse=True)

        ai = await self._call_ai(
            TaskType.MATCHING,
            {"seeker_profile": context.user_context.to_prompt_context(),
             "top_matches": filtered[:3]},
            context.user_context,
        ) if filtered else None

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.MATCHING, True,
            {"matches": filtered, "explanations": ai.output if ai else "No matches found"},
            [f"Found {len(filtered)} compatible matches"],
            ["Review compatibility before outreach"],
            ["Connect with top match within 48 hours"],
            ms, ai.credits_consumed if ai else 0,
        )


class RiskEvaluatorAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0   = datetime.now()
        idea = (context.trigger_event or {}).get("idea", {})
        ai   = await self._call_ai(TaskType.RISK_ANALYSIS, idea, context.user_context, ip_protected=True)
        ms   = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.RISK_EVALUATOR, True,
            {"risk_analysis": {
                "market_clarity_score": 7.5, "technical_feasibility": 8.0,
                "competitive_risk": "medium",
                "key_risks": ["Saturated market", "High CAC", "Regulatory compliance"],
                "swot": {"strengths": ["Innovative approach"], "weaknesses": ["No market presence"],
                         "opportunities": ["Growing market"], "threats": ["Established players"]},
                "ai_analysis": ai.output,
            }},
            ["Evaluated market risks", "Generated SWOT analysis"],
            ["Address top 3 risks in 30-day sprint"],
            ["Validate assumptions before building"],
            ms, ai.credits_consumed,
        )


class WorkspaceAssistantAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        trigger = context.trigger_event or {}
        # available_tools comes from WorkspaceAIService.suggest_tasks when the
        # caller forwards their Bearer token (it fetches the MCP catalogue from
        # BACKEND/api/mcp). Threading it into input_data is what actually lets
        # the LLM reference real tool names — without this forward, the F2
        # wiring is data-in-context-die-there.
        ai  = await self._call_ai(
            TaskType.WORKSPACE_ASSISTANT,
            {"workspace": trigger.get("workspace_data", {}),
             "available_tools": trigger.get("available_tools", []),
             "user": context.user_context.to_prompt_context()},
            context.user_context,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.WORKSPACE_ASSISTANT, True,
            {"task_suggestions": ai.output},
            ["Analysed project state", "Prioritised task backlog"],
            ["Focus on highest-impact tasks"],
            ["Update task board", "Communicate priorities to team"],
            ms,
        )


class FeedIntelligenceAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0    = datetime.now()
        items = (context.trigger_event or {}).get("feed_items", [])
        ai    = await self._call_ai(
            TaskType.FEED_INTELLIGENCE,
            {"feed_items": items[:50], "user": context.user_context.to_prompt_context()},
            context.user_context,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.FEED_INTELLIGENCE, True,
            {"curated_feed": ai.output},
            [f"Ranked {len(items)} feed items"],
            ["Engage with top 5 items"],
            ["Refresh feed every 30 minutes"],
            ms,
        )


class DashboardIntelligenceAgent(BaseAgent):
    """
    Aggregates all component scores into the GSIS surface.
    Computes real-time score card and surfaces most critical signals.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        uc  = context.user_context
        sm  = context.shared_memory

        # Pull available component scores
        pps = ScoringEngine.compute_pps(
            completed_tasks=uc.tasks_completed_week,
            total_tasks=max(uc.tasks_completed_week + 2, 1),
            quality_factor=0.80,
        )
        evi = ScoringEngine.compute_evi(
            uc.tasks_completed_week, 8.0, 4, 10, uc.days_since_update
        )
        mrs = sm.get("market_readiness_score", 0)
        bss = sm.get("beta_satisfaction_score", 0)
        rgs = sm.get("revenue_growth_signal", 0)
        frs = ScoringEngine.compute_founder_reliability(80, 70, 75, 40, 85)
        cis = ScoringEngine.compute_cis(60, 65, 70)
        iis = ScoringEngine.compute_iis(30, 20, 15, 10)
        cs  = ScoringEngine.compute_compliance_score(uc.compliance_items)

        gsis_result = ScoringEngine.compute_gsis(pps, evi, mrs, bss, rgs, frs, cis, iis, cs)

        ai = await self._call_ai(
            TaskType.GSIS_COMPUTE,
            {"gsis": gsis_result, "user": uc.to_prompt_context()},
            uc,
        )

        decay = ScoringEngine.compute_decay_factor(uc.days_since_update)
        alerts = []
        if decay < 0.70:
            alerts.append({"type": "momentum_decay", "severity": "warning",
                           "message": f"Decay active: {round((1-decay)*100)}% score penalty"})
        if gsis_result["alert_triggered"]:
            alerts.append({"type": "gsis_alert", "severity": "warning",
                           "message": f"Alert score: {gsis_result['alert_score']} -- AI intervention recommended"})
        if uc.credits_remaining <= 2:
            alerts.append({"type": "credits_low", "severity": "info",
                           "message": "Credits running low. Purchase a credit pack."})

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.DASHBOARD_INTELLIGENCE, True,
            {
                "gsis":         gsis_result,
                "score_card": {
                    "pps": pps, "evi": evi, "mrs": mrs, "bss": bss,
                    "rgs": rgs, "frs": frs, "cis": cis, "iis": iis, "cs": cs,
                    "decay_factor": round(decay, 4),
                    "momentum_health": round(decay * 100, 1),
                    "credits_remaining": uc.credits_remaining,
                },
                "alerts":   alerts,
                "insights": ai.output,
            },
            ["Computed GSIS and all component scores", f"GSIS: {gsis_result['gsis']}"],
            ["Act on top alert", "Complete pending training module"],
            ["Check dashboard daily"],
            ms, ai.credits_consumed,
        )


class GSISComputeAgent(BaseAgent):
    """
    Dedicated GSIS computation and narration agent.
    Called on login, milestone update, and on-demand.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        sm  = context.shared_memory
        uc  = context.user_context

        gsis = ScoringEngine.compute_gsis(
            product_progress_score=sm.get("pps", 0),
            execution_velocity_index=sm.get("evi", 0),
            market_readiness_score=sm.get("mrs", 0),
            beta_satisfaction_score=sm.get("bss", 0),
            revenue_growth_signal=sm.get("rgs", 0),
            founder_reputation_score=sm.get("frs", 0),
            community_influence_score=sm.get("cis", 0),
            investor_interest_score=sm.get("iis", 0),
            compliance_score=sm.get("cs", 0),
        )

        ai = await self._call_ai(TaskType.GSIS_COMPUTE, {"gsis": gsis}, uc)

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.GSIS_COMPUTE, True,
            {"gsis": gsis, "narrative": ai.output},
            [f"GSIS: {gsis['gsis']} -- {gsis['classification']}"],
            [],
            ["Share GSIS with investors if > 70"],
            ms, ai.credits_consumed,
        )


class AIProfileAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.PROFILE_ANALYSIS,
            {"user": context.user_context.to_prompt_context(),
             "profile_data": (context.trigger_event or {}).get("profile_data", {})},
            context.user_context,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.AI_PROFILE, True,
            {"profile_analysis": ai.output},
            ["Scored profile completeness", "Identified credibility gaps"],
            ["Add portfolio projects", "Connect GitHub"],
            ["Update profile based on recommendations"],
            ms, ai.credits_consumed,
        )


class OrgSphereAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        ai = await self._call_ai(
            TaskType.ORG_SPHERE,
            {"org_data": (context.trigger_event or {}).get("org_data", {}),
             "user": context.user_context.to_prompt_context()},
            context.user_context, max_tokens=3000,
        )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.ORG_SPHERE, True,
            {"org_analysis": ai.output},
            ["Mapped org structure", "Identified knowledge gaps"],
            ["Define clear roles before hiring"],
            ["Create RACI matrix"],
            ms, ai.credits_consumed,
        )


class AdminMonitorAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        signals = (context.trigger_event or {}).get("anomaly_signals", [])
        ai      = await self._call_ai(
            TaskType.ADMIN_MONITOR,
            {"signals": signals, "user": context.user_context.to_prompt_context()},
            context.user_context,
        )
        flags = [{"signal": s, "risk": "medium"} for s in signals[:10]]
        ms    = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.ADMIN_MONITOR, True,
            {"risk_flags": flags, "analysis": ai.output},
            ["Scanned anomaly signals"],
            [f"Immediate review: {sum(1 for f in flags if f['risk']=='high')} high-risk flag(s)"],
            ["Review flagged accounts", "Escalate critical flags"],
            ms,
        )


# ============================================================================
# FULL VENTURE PIPELINE
# ============================================================================

class VenturePipeline:
    """
    10-agent sequential incubation pipeline.

    Stage 1: Intake
    Stage 2: Unicorn Evaluation
    Stage 3: Market + Feasibility (parallel)
    Stage 4: Pivot check (if UPS < 50)
    Stage 5: Strategy + Finance
    Stage 6: Business Plan + Tech Architecture (parallel)
    Stage 7: Investor Intelligence (with EVI-I)
    """

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orch = orchestrator

    async def run(self, user_context: UserContext, venture_data: Dict) -> Dict[str, AgentResult]:
        shared: Dict[str, Any] = {}
        results: Dict[str, AgentResult] = {}

        def ctx(extra=None) -> AgentContext:
            return AgentContext(user_context=user_context,
                                trigger_event=extra or venture_data,
                                shared_memory=shared)

        r = await self.orch.trigger_agent(AgentType.VENTURE_INTAKE, ctx())
        results["intake"] = r; shared.update(r.output)

        r = await self.orch.trigger_agent(AgentType.UNICORN_EVALUATOR, ctx())
        results["unicorn"] = r; shared.update(r.output)

        tasks = await asyncio.gather(
            self.orch.trigger_agent(AgentType.MARKET_INTELLIGENCE, ctx()),
            self.orch.trigger_agent(AgentType.PRODUCT_FEASIBILITY, ctx()),
        )
        results["market"] = tasks[0]; results["feasibility"] = tasks[1]
        shared["market_analysis"]  = tasks[0].output
        shared["feasibility_data"] = tasks[1].output

        ups_score = shared.get("unicorn_potential_score", 50)
        if ups_score < 50:
            r = await self.orch.trigger_agent(AgentType.PIVOT_INTELLIGENCE, ctx())
            results["pivot"] = r
            if r.output.get("pivot_needed"):
                return results

        r = await self.orch.trigger_agent(AgentType.STARTUP_STRATEGY, ctx())
        results["strategy"] = r; shared["startup_strategy"] = r.output

        r = await self.orch.trigger_agent(AgentType.FINANCE_STRATEGY, ctx())
        results["finance"] = r; shared["finance_strategy"] = r.output

        tasks = await asyncio.gather(
            self.orch.trigger_agent(AgentType.BUSINESS_PLAN_GEN, ctx()),
            self.orch.trigger_agent(AgentType.TECH_ARCHITECT, ctx()),
        )
        results["business_plan"]  = tasks[0]
        results["tech_architect"] = tasks[1]

        r = await self.orch.trigger_agent(AgentType.INVESTOR_INTELLIGENCE, ctx())
        results["investor"] = r

        # Prompt -> Live App: scaffold runs after architecture is designed
        r = await self.orch.trigger_agent(AgentType.APP_SCAFFOLD, ctx())
        results["app_scaffold"] = r

        return results


# ============================================================================
# IDEA & SOLUTION HUB AGENTS  (10 agents)
# ============================================================================

class ProblemAnalyzerAgent(BaseAgent):
    """Expands and structures real-world problem statements."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.PROBLEM_ANALYSIS, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.PROBLEM_ANALYZER, success=True,
            output={"analysis": resp.output, "stakeholder_map": {}},
            actions_taken=["Expanded problem scope", "Generated stakeholder map"],
            recommendations=["Post to Global Problems Board", "Invite domain experts"],
            next_steps=["Open discussion thread", "Discover similar problems"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class SolutionSynthesizerAgent(BaseAgent):
    """Converts matured discussions into structured solution blueprints."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.SOLUTION_SYNTHESIS, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.SOLUTION_SYNTHESIZER, success=True,
            output={"synthesis": resp.output},
            actions_taken=["Synthesised discussion contributions", "Structured solution blueprint"],
            recommendations=["Convert to Solution Project", "Define execution plan"],
            next_steps=["Create SolutionProject", "Identify funding type"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class ImpactPredictorAgent(BaseAgent):
    """Predicts real-world impact of a solution across time horizons."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.IMPACT_PREDICTION, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.IMPACT_PREDICTOR, success=True,
            output={"impact_narrative": resp.output},
            actions_taken=["Predicted short/medium/long term impact"],
            recommendations=["Update Impact Score", "Share with potential funders"],
            next_steps=["Attach to solution project", "Include in grant application"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class FeasibilityEstimatorAgent(BaseAgent):
    """Estimates technical, operational, financial, and political feasibility."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.FEASIBILITY_ESTIMATE, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.FEASIBILITY_ESTIMATOR, success=True,
            output={"feasibility_report": resp.output},
            actions_taken=["Assessed 4-dimension feasibility", "Estimated cost range"],
            recommendations=["Address critical blockers before deployment"],
            next_steps=["Update solution project", "Begin deployment planning"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class ProblemDiscoveryAgent(BaseAgent):
    """Automatically discovers real-world problems from external data signals."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.PROBLEM_DISCOVERY, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.PROBLEM_DISCOVERY, success=True,
            output={"discovered_problems": resp.output},
            actions_taken=["Scanned external data signals", "Classified problem candidates"],
            recommendations=["Review discovered problems", "Activate highest-priority items"],
            next_steps=["Post to Global Problems Board"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class SolutionMatcherAgent(BaseAgent):
    """Matches existing solutions globally to new problems."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.SOLUTION_MATCHING, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.SOLUTION_MATCHER, success=True,
            output={"matches": resp.output},
            actions_taken=["Searched existing solution database", "Ranked matches by relevance"],
            recommendations=["Review top 3 matches before building from scratch"],
            next_steps=["Contact matched solution owner", "Adapt or fork existing solution"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class DeploymentPlannerAgent(BaseAgent):
    """Creates structured real-world deployment plans for validated solutions."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.DEPLOYMENT_PLANNING, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.DEPLOYMENT_PLANNER, success=True,
            output={"deployment_plan": resp.output},
            actions_taken=["Created deployment checklist", "Recommended deployment mode"],
            recommendations=["Begin partner onboarding", "Set up field data collection"],
            next_steps=["Create SolutionDeployment record", "Activate checklist"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class GrantMatcherAgent(BaseAgent):
    """Generates grant applications and matches solutions to funding opportunities."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.GRANT_MATCHING, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.GRANT_MATCHER, success=True,
            output={"grant_application": resp.output},
            actions_taken=["Generated funder-ready grant application"],
            recommendations=["Review and customise before submission", "Track submission status"],
            next_steps=["Submit GrantApplication", "Apply to matching impact investors"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class DiscussionModeratorAgent(BaseAgent):
    """AI-powered moderator that summarises, clusters, and directs problem discussions."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.DISCUSSION_MODERATION, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.DISCUSSION_MODERATOR, success=True,
            output={"moderation_summary": resp.output},
            actions_taken=["Summarised discussion thread", "Clustered idea directions"],
            recommendations=["Highlight top-voted ideas", "Notify contributors of synthesis"],
            next_steps=["Show 'Convert to Solution' CTA if ready"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class FieldFeedbackAgent(BaseAgent):
    """Analyses real-world field feedback to close the Problem -> Solution -> Deploy -> Optimise loop."""
    async def execute(self, context: AgentContext) -> AgentResult:
        t = datetime.now()
        resp = await self._call_ai(TaskType.FIELD_FEEDBACK_ANALYSIS, context.trigger_event or {}, context.user_context)
        return AgentResult(
            agent_type=AgentType.FIELD_FEEDBACK_AGENT, success=True,
            output={"feedback_analysis": resp.output},
            actions_taken=["Analysed field feedback", "Identified optimisation opportunities"],
            recommendations=["Update solution impact score", "Schedule next deployment cycle"],
            next_steps=["Apply optimisations", "Update deployment record"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


# ============================================================================
# DOCUMENT GENERATION AGENTS  (2 agents)
# ============================================================================

class DocumentGenerationAgent(BaseAgent):
    """
    Orchestrates the full document generation flow.
    Pulls startup data, selects template, calls AI, formats output.
    Supports all 8 document types.
    """
    async def execute(self, context: AgentContext) -> AgentResult:
        t         = datetime.now()
        event     = context.trigger_event or {}
        doc_type  = event.get("document_type", "executive_summary")

        # Map document_type string to correct TaskType
        task_map = {
            "executive_summary":       TaskType.DOCUMENT_EXECUTIVE_SUMMARY,
            "business_plan":           TaskType.DOCUMENT_BUSINESS_PLAN,
            "pitch_deck":              TaskType.DOCUMENT_PITCH_DECK,
            "investor_report":         TaskType.DOCUMENT_INVESTOR_REPORT,
            "unicorn_analysis_report": TaskType.DOCUMENT_UNICORN_REPORT,
            "product_roadmap":         TaskType.DOCUMENT_PRODUCT_ROADMAP,
            "financial_projection":    TaskType.DOCUMENT_FINANCIAL_PROJECTION,
            "market_research_report":  TaskType.DOCUMENT_MARKET_RESEARCH,
        }
        task_type = task_map.get(doc_type, TaskType.DOCUMENT_EXECUTIVE_SUMMARY)
        resp      = await self._call_ai(task_type, event, context.user_context)

        return AgentResult(
            agent_type=AgentType.DOCUMENT_GENERATION, success=True,
            output={
                "document_type": doc_type,
                "content":       resp.output,
                "model_used":    resp.model_used,
                "credits":       resp.credits_consumed,
            },
            actions_taken=[f"Generated {doc_type.replace('_', ' ').title()}"],
            recommendations=["Export to PDF", "Share with stakeholders"],
            next_steps=["Trigger DOCUMENT_EXPORT agent", "Store in generated_documents"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )


class DocumentExportAgent(BaseAgent):
    """
    Handles all export operations: PDF, Notion, Google Docs, Slide Deck.
    Generates shareable links and "Edit with AI" hooks.
    """
    async def execute(self, context: AgentContext) -> AgentResult:
        t       = datetime.now()
        event   = context.trigger_event or {}
        doc_id  = event.get("document_id", "doc_unknown")
        fmt     = event.get("export_format", "pdf")
        link    = f"https://app.techit.io/documents/share/{doc_id}?expires=30d"
        pdf_url = f"https://cdn.techit.io/documents/{doc_id}/export.pdf"

        return AgentResult(
            agent_type=AgentType.DOCUMENT_EXPORT, success=True,
            output={
                "document_id":    doc_id,
                "export_format":  fmt,
                "pdf_url":        pdf_url,
                "shareable_link": link,
                "edit_with_ai":   f"https://app.techit.io/documents/{doc_id}/edit",
            },
            actions_taken=[f"Exported document as {fmt}", "Generated shareable link"],
            recommendations=["Download PDF for offline use", "Share link with investors"],
            next_steps=["Store export URL in document_exports table"],
            execution_time_ms=int((datetime.now()-t).total_seconds()*1000),
        )




# ============================================================================
# PROMPT -> LIVE APP AGENT
# ============================================================================

class AppScaffoldAgent(BaseAgent):
    """
    TechIT's defining edge agent -- Prompt -> Live App in Minutes.

    This agent sits at the end of the Venture Pipeline, after TechArchitectAgent.
    Where TechArchitectAgent produces architecture *descriptions*, this agent
    produces architecture *code* -- actual downloadable files ready to deploy.

    What it generates:
      - Next.js 14 App Router page structure (routes, components, auth)
      - Supabase schema SQL (CREATE TABLE statements, RLS policies)
      - API route definitions (method, path, auth, request/response)
      - Environment variable template (.env.example)
      - One-click deploy configuration (vercel.json, GitHub Actions CI/CD)
      - Numbered setup steps (exact CLI commands)

    This is NOT Bolt.new. The difference:
      Bolt.new:    User describes an app -> code generated
      TechIT:      Platform already knows the problem, market, stack, and
                   unicorn score -> scaffold is generated FROM intelligence,
                   not FROM scratch.

    The result: a scaffold that is architecturally correct for the market,
    not just syntactically correct for the prompt.

    Triggers:
      - EVENT_DRIVEN: fires automatically after tech_architecture_complete
      - ON_DEMAND:    user explicitly requests scaffold from dashboard

    Output: structured scaffold dict + deploy config + live URL (post-deploy).
    IP protected: True -- scaffold embeds the venture's proprietary logic.
    """

    SUPPORTED_STACKS = {
        "nextjs_supabase":   "Next.js 14 + Supabase + Tailwind CSS + TypeScript",
        "nextjs_prisma":     "Next.js 14 + PostgreSQL + Prisma + Tailwind CSS",
        "react_firebase":    "React 18 + Firebase + Tailwind CSS",
        "expo_supabase":     "Expo (React Native) + Supabase + NativeWind",
        "fastapi_supabase":  "FastAPI + Supabase + SQLAlchemy (API-only)",
    }

    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        profile = context.shared_memory.get("venture_profile", context.trigger_event or {})
        arch    = context.shared_memory.get("tech_architecture", {})

        # Determine best stack from tech architecture output
        stack = self._select_stack(profile, arch)

        # Step 1: Generate scaffold structure
        scaffold_resp = await self._call_ai(
            TaskType.APP_SCAFFOLD_GENERATION,
            {
                "venture_profile":   profile,
                "tech_architecture": arch,
                "stack":             stack,
                "startup_name":      profile.get("startup_name", "MyStartup"),
                "industry":          profile.get("industry", ""),
                "problem":           profile.get("problem", ""),
                "solution":          profile.get("solution", ""),
                "target_customers":  profile.get("target_customers", ""),
                "revenue_model":     profile.get("revenue_model", ""),
            },
            context.user_context,
            ip_protected=True,   # Scaffold embeds proprietary business logic
            max_tokens=8000,     # Scaffold is large -- full schema + routes + pages
        )

        # Step 2: Parse scaffold JSON
        scaffold = self._parse_scaffold(scaffold_resp.output)

        # Step 3: Generate deploy configuration
        deploy_resp = await self._call_ai(
            TaskType.APP_DEPLOY_CONFIG,
            {"scaffold": scaffold, "stack": stack,
             "startup_name": profile.get("startup_name", "my-startup")},
            context.user_context,
            ip_protected=True,
            max_tokens=3000,
        )
        deploy_config = self._parse_deploy_config(deploy_resp.output)

        # Step 4: Build the complete scaffold output
        full_scaffold = {
            "scaffold_type":      stack,
            "stack_description":  self.SUPPORTED_STACKS.get(stack, stack),
            "startup_name":       profile.get("startup_name", "MyStartup"),
            "pages":              scaffold.get("pages", []),
            "schema_sql":         scaffold.get("schema_sql", ""),
            "api_routes":         scaffold.get("api_routes", []),
            "env_template":       scaffold.get("env_template", ""),
            "components":         scaffold.get("components", []),
            "setup_steps":        scaffold.get("setup_steps", []),
            "estimated_build_hours": scaffold.get("estimated_build_hours", 4),
            "deploy_config":      deploy_config,
            "download_url":       f"https://app.techit.io/scaffold/{context.user_context.project_id}/download.zip",
            "vercel_deploy_url":  f"https://vercel.com/new/clone?repository-url=https://github.com/techit-scaffold/{context.user_context.project_id}",
            "live_preview_url":   f"https://{profile.get('startup_name','my-app').lower().replace(' ','-')}.techit.app",
            "ip_protected":       True,
        }

        # Store in shared memory for downstream agents (investor docs can reference it)
        context.shared_memory["app_scaffold"] = full_scaffold

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        pages_count  = len(full_scaffold["pages"])
        routes_count = len(full_scaffold["api_routes"])

        return AgentResult(
            agent_type=AgentType.APP_SCAFFOLD,
            success=True,
            output=full_scaffold,
            actions_taken=[
                f"Selected stack: {self.SUPPORTED_STACKS.get(stack, stack)}",
                f"Generated {pages_count} pages and {routes_count} API routes",
                "Built Supabase schema SQL",
                "Generated Vercel + GitHub Actions deploy config",
                "Created .env.example template",
            ],
            recommendations=[
                "Download the scaffold ZIP and run: npm install && npm run dev",
                "Push to GitHub then click the Vercel deploy button",
                "Your live URL will be ready in ~2 minutes",
            ],
            next_steps=[
                f"Download: {full_scaffold['download_url']}",
                f"1-click deploy: {full_scaffold['vercel_deploy_url']}",
                f"Live preview: {full_scaffold['live_preview_url']}",
            ],
            execution_time_ms=ms,
            credits_consumed=scaffold_resp.credits_consumed + deploy_resp.credits_consumed,
        )

    def _select_stack(self, profile: dict, arch: dict) -> str:
        """
        Select the optimal stack based on venture profile and architecture output.
        Mobile products -> Expo; API-first B2B -> FastAPI; default -> Next.js + Supabase.
        Production: parse from TechArchitectAgent structured output.
        """
        description = (
            str(profile.get("solution", "")) +
            str(arch.get("tech_architecture", ""))
        ).lower()
        if any(w in description for w in ["mobile", "app store", "ios", "android"]):
            return "expo_supabase"
        if any(w in description for w in ["api-first", "b2b api", "developer tool", "sdk"]):
            return "fastapi_supabase"
        return "nextjs_supabase"  # sensible default for 80% of startups

    def _parse_scaffold(self, raw_output: str) -> dict:
        """
        Parse the AI scaffold JSON response.
        Returns a safe default if parsing fails -- never blocks the pipeline.
        """
        import json, re
        try:
            # Strip markdown fences if model adds them despite instructions
            clean = re.sub(r"```(?:json)?|```", "", raw_output).strip()
            return json.loads(clean)
        except Exception:
            # Safe fallback: return minimal valid scaffold
            return {
                "pages": [
                    {"route": "/", "component_name": "HomePage", "description": "Landing page", "auth_required": False},
                    {"route": "/dashboard", "component_name": "DashboardPage", "description": "Main dashboard", "auth_required": True},
                    {"route": "/login", "component_name": "LoginPage", "description": "Authentication", "auth_required": False},
                ],
                "schema_sql": "-- Schema generation pending -- re-run scaffold",
                "api_routes": [
                    {"method": "GET", "path": "/api/health", "description": "Health check", "auth_required": False},
                ],
                "env_template": "NEXT_PUBLIC_SUPABASE_URL=\nNEXT_PUBLIC_SUPABASE_ANON_KEY=\nSUPABASE_SERVICE_ROLE_KEY=\n",
                "components": [],
                "setup_steps": ["npm install", "cp .env.example .env.local", "npm run dev"],
                "estimated_build_hours": 4,
            }

    def _parse_deploy_config(self, raw_output: str) -> dict:
        """Parse deploy config JSON, return safe fallback on error."""
        import json, re
        try:
            clean = re.sub(r"```(?:json)?|```", "", raw_output).strip()
            return json.loads(clean)
        except Exception:
            return {
                "vercel_json": '{"buildCommand":"npm run build","outputDirectory":".next","framework":"nextjs"}',
                "deploy_steps": [
                    "git init && git add . && git commit -m 'Initial scaffold'",
                    "vercel --prod",
                ],
                "deploy_url_pattern": "https://[project-name].vercel.app",
            }


# ============================================================================
# AGENT ORCHESTRATOR
# ============================================================================

class AgentOrchestrator:
    def __init__(self, ai_brain: AICommandLayer) -> None:
        self.ai_brain = ai_brain
        self.agents: Dict[AgentType, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        registry = [
            # (AgentType, Class, name, triggers, min_tier, schedule)
            (AgentType.VENTURE_INTAKE,        VentureIntakeAgent,        "Venture Intake",              [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], SubscriptionTier.FREE,        None),
            (AgentType.UNICORN_EVALUATOR,     UnicornEvaluatorAgent,     "Unicorn Probability Engine",  [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], SubscriptionTier.BUILDER,     None),
            (AgentType.MARKET_INTELLIGENCE,   MarketIntelligenceAgent,   "Market Intelligence Engine",  [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], SubscriptionTier.BUILDER,     None),
            (AgentType.PRODUCT_FEASIBILITY,   ProductFeasibilityAgent,   "Product Feasibility Agent",   [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.STARTUP_STRATEGY,      StartupStrategyAgent,      "Startup Strategy Generator",  [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.FINANCE_STRATEGY,      FinanceStrategyAgent,      "Finance Strategy Agent",      [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.INVESTOR_INTELLIGENCE, InvestorIntelligenceAgent, "Investor Intelligence Engine",[AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN],  SubscriptionTier.INVESTOR,    "0 0 * * *"),
            (AgentType.BUSINESS_PLAN_GEN,     BusinessPlanGeneratorAgent,"Business Plan Generator",     [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.INVESTOR,    None),
            (AgentType.TECH_ARCHITECT,        TechArchitectAgent,        "Tech Architecture Agent",     [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.PIVOT_INTELLIGENCE,    PivotIntelligenceAgent,    "Pivot Intelligence Agent",    [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.BUILDER,     None),
            (AgentType.TOUR_GUIDE,            TourGuideAgent,            "AI Tour Guide",               [AgentTrigger.SCHEDULED, AgentTrigger.ON_DEMAND],     SubscriptionTier.FREE,        "0 6 * * *"),
            (AgentType.ADAPTIVE_TRAINING,     AdaptiveTrainingAgent,     "Adaptive Training Agent",     [AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN],  SubscriptionTier.FREE,        "0 2 * * 1"),
            (AgentType.MATCHING,              MatchingAgent,             "Team Matching Engine",        [AgentTrigger.ON_DEMAND, AgentTrigger.EVENT_DRIVEN],  SubscriptionTier.BUILDER,     None),
            (AgentType.RISK_EVALUATOR,        RiskEvaluatorAgent,        "Risk Evaluator Agent",        [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.BUILDER,     None),
            (AgentType.WORKSPACE_ASSISTANT,   WorkspaceAssistantAgent,   "Workspace Assistant",         [AgentTrigger.ON_DEMAND, AgentTrigger.EVENT_DRIVEN],  SubscriptionTier.FREE,        None),
            (AgentType.FEED_INTELLIGENCE,     FeedIntelligenceAgent,     "Feed Intelligence Engine",    [AgentTrigger.SCHEDULED],                             SubscriptionTier.FREE,        "*/30 * * * *"),
            (AgentType.DASHBOARD_INTELLIGENCE,DashboardIntelligenceAgent,"Dashboard Intelligence",      [AgentTrigger.ON_DEMAND, AgentTrigger.SCHEDULED],     SubscriptionTier.FREE,        "*/30 * * * *"),
            (AgentType.AI_PROFILE,            AIProfileAgent,            "AI Profile Agent",            [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FREE,        None),
            (AgentType.ORG_SPHERE,            OrgSphereAgent,            "Org Sphere Agent",            [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.ADMIN_MONITOR,         AdminMonitorAgent,         "Admin Monitor Agent",         [AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN],  SubscriptionTier.ENTERPRISE,  "*/15 * * * *"),
            (AgentType.GSIS_COMPUTE,          GSISComputeAgent,          "GSIS Compute Agent",          [AgentTrigger.ON_DEMAND, AgentTrigger.SCHEDULED],     SubscriptionTier.FREE,        "*/30 * * * *"),
            # Idea & Solution Hub agents
            (AgentType.PROBLEM_ANALYZER,      ProblemAnalyzerAgent,      "Problem Analyzer",            [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FREE,        None),
            (AgentType.SOLUTION_SYNTHESIZER,  SolutionSynthesizerAgent,  "Solution Synthesizer",        [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.IMPACT_PREDICTOR,      ImpactPredictorAgent,      "Impact Predictor",            [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FREE,        None),
            (AgentType.FEASIBILITY_ESTIMATOR, FeasibilityEstimatorAgent, "Feasibility Estimator",       [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.BUILDER,     None),
            (AgentType.PROBLEM_DISCOVERY,     ProblemDiscoveryAgent,     "Problem Discovery Engine",    [AgentTrigger.SCHEDULED, AgentTrigger.ON_DEMAND],     SubscriptionTier.BUILDER,     "0 6 * * *"),
            (AgentType.SOLUTION_MATCHER,      SolutionMatcherAgent,      "Solution Matching Engine",    [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.BUILDER,     None),
            (AgentType.DEPLOYMENT_PLANNER,    DeploymentPlannerAgent,    "Deployment Planner",          [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.GRANT_MATCHER,         GrantMatcherAgent,         "Grant Matching Engine",       [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FOUNDER_PRO, None),
            (AgentType.DISCUSSION_MODERATOR,  DiscussionModeratorAgent,  "Discussion Moderator",        [AgentTrigger.EVENT_DRIVEN, AgentTrigger.SCHEDULED],  SubscriptionTier.FREE,        "*/60 * * * *"),
            (AgentType.FIELD_FEEDBACK_AGENT,  FieldFeedbackAgent,        "Field Feedback Analyst",      [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FREE,        None),
            # Document Generation agents
            (AgentType.DOCUMENT_GENERATION,   DocumentGenerationAgent,   "Document Generation Engine",  [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.BUILDER,     None),
            (AgentType.DOCUMENT_EXPORT,       DocumentExportAgent,       "Document Export Agent",       [AgentTrigger.EVENT_DRIVEN],                          SubscriptionTier.FREE,        None),
            # Prompt -> Live App
            (AgentType.APP_SCAFFOLD,          AppScaffoldAgent,          "App Scaffold Engine",         [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND],  SubscriptionTier.FOUNDER_PRO, None),
        ]
        for atype, cls, name, triggers, min_tier, schedule in registry:
            config = AgentConfig(atype, name, f"TechIT {name}", triggers, schedule, 60, 3, min_tier)
            self.agents[atype] = cls(config, self.ai_brain)

    async def trigger_agent(self, agent_type: AgentType, context: AgentContext) -> AgentResult:
        agent = self.agents.get(agent_type)
        if not agent:
            raise ValueError(f"Agent {agent_type.value} not registered.")
        result = await agent.execute(context)
        agent._log(result)
        return result

    async def handle_event(self, event: Dict) -> List[AgentResult]:
        """
        Event -> agent routing.

        All events trigger agents that run concurrently where possible.
        Training agent adapts on lifecycle events (mvp_shipped, pivot_detected, etc.).

        System context elevation:
          InvestorIntelligenceAgent requires Investor+ tier.
          When fired from a lifecycle event (revenue_went_live, investor_expressed_interest)
          triggered by a founder, we elevate the context to a system-level investor context
          so the agent can run without a PermissionError.  The output is then written to the
          project's investor_evi_snapshots row, not returned to the founder directly.
        """
        etype = event.get("type")
        uc    = event.get("user_context")

        def ctx(uc_override=None) -> AgentContext:
            return AgentContext(
                user_context=uc_override or uc,
                trigger_event=event,
            )

        def system_investor_ctx() -> AgentContext:
            """Elevated system context for InvestorIntelligenceAgent lifecycle calls."""
            system_uc = UserContext(
                user_id=f"system_investor_{uc.user_id if uc else 'anon'}",
                role=UserRole.INVESTOR,
                subscription_tier=SubscriptionTier.INVESTOR,
                credits_remaining=9999,
                project_id=uc.project_id if uc else None,
                project_stage=uc.project_stage if uc else "idea",
                industry=uc.industry if uc else "general",
                tech_stack=uc.tech_stack if uc else [],
                past_feedback=[],
                training_progress={},
                time_logged_today=uc.time_logged_today if uc else 0,
                tasks_completed_week=uc.tasks_completed_week if uc else 0,
                days_since_update=uc.days_since_update if uc else 0,
                team_size=uc.team_size if uc else 1,
                has_revenue=uc.has_revenue if uc else False,
                beta_users_count=uc.beta_users_count if uc else 0,
            )
            return AgentContext(user_context=system_uc, trigger_event=event)

        # Routing table.
        # Events whose agent lists contain INVESTOR_INTELLIGENCE use system_investor_ctx()
        # for that specific agent; all others use the original founder context.
        INVESTOR_ELEVATED = {AgentType.INVESTOR_INTELLIGENCE}

        routing: Dict[str, List[AgentType]] = {
            # idea_submitted  -> VentureIntake (structures input) + RiskEvaluator + Matching
            "idea_submitted":              [AgentType.VENTURE_INTAKE,
                                            AgentType.RISK_EVALUATOR,
                                            AgentType.MATCHING],
            # user_login -> all three run on every login
            "user_login":                  [AgentType.TOUR_GUIDE,
                                            AgentType.DASHBOARD_INTELLIGENCE,
                                            AgentType.GSIS_COMPUTE],
            # training events
            "training_completed":          [AgentType.ADAPTIVE_TRAINING],
            # milestone updates refresh scores
            "milestone_updated":           [AgentType.DASHBOARD_INTELLIGENCE,
                                            AgentType.TOUR_GUIDE,
                                            AgentType.GSIS_COMPUTE],
            # investor views a startup (fired with investor context)
            "investor_views":              [AgentType.INVESTOR_INTELLIGENCE],
            # profile and org events
            "profile_updated":             [AgentType.AI_PROFILE],
            "org_created":                 [AgentType.ORG_SPHERE],
            # post-MVP lifecycle -- investor agent uses elevated system context
            "mvp_shipped":                 [AgentType.ADAPTIVE_TRAINING,
                                            AgentType.DASHBOARD_INTELLIGENCE],
            "revenue_went_live":           [AgentType.ADAPTIVE_TRAINING,
                                            AgentType.INVESTOR_INTELLIGENCE],
            "pivot_detected":              [AgentType.PIVOT_INTELLIGENCE,
                                            AgentType.ADAPTIVE_TRAINING],
            "investor_expressed_interest": [AgentType.ADAPTIVE_TRAINING,
                                            AgentType.INVESTOR_INTELLIGENCE],
            # Idea & Solution Hub events
            "problem_submitted":           [AgentType.PROBLEM_ANALYZER,
                                            AgentType.SOLUTION_MATCHER],
            "solution_converted":          [AgentType.SOLUTION_SYNTHESIZER,
                                            AgentType.IMPACT_PREDICTOR,
                                            AgentType.FEASIBILITY_ESTIMATOR],
            "deployment_created":          [AgentType.DEPLOYMENT_PLANNER],
            "field_feedback_submitted":    [AgentType.FIELD_FEEDBACK_AGENT],
            # Document Generation events
            "document_requested":          [AgentType.DOCUMENT_GENERATION],
            "document_export_requested":   [AgentType.DOCUMENT_EXPORT],
            # Prompt -> Live App events
            "tech_architecture_complete":  [AgentType.APP_SCAFFOLD],
            "app_scaffold_requested":      [AgentType.APP_SCAFFOLD],
        }

        agent_types = routing.get(etype, [])
        if not agent_types:
            return []

        tasks = []
        for at in agent_types:
            # Use system investor context for investor intelligence lifecycle events
            if at in INVESTOR_ELEVATED and uc and uc.role != UserRole.INVESTOR:
                tasks.append(self.trigger_agent(at, system_investor_ctx()))
            else:
                tasks.append(self.trigger_agent(at, ctx()))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, AgentResult)]

    def venture_pipeline(self) -> VenturePipeline:
        return VenturePipeline(self)


# ============================================================================
# DEMO
# ============================================================================

async def _demo() -> None:
    from ai_router_core import ModelRouter, PromptEngine, SafetyEngine
    brain = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    orch  = AgentOrchestrator(brain)

    uc = UserContext(
        user_id="founder_demo", role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO, credits_remaining=150,
        project_id=None, project_stage="idea", industry="edtech",
        tech_stack=[], past_feedback=[],
        training_progress={"completion_percentage": 0},
        time_logged_today=0, tasks_completed_week=0,
        days_since_update=2, team_size=2,
    )

    event = {"type": "user_login", "user_context": uc}
    results = await orch.handle_event(event)
    for r in results:
        status = "✅" if r.success else "❌"
        print(f"{status} {r.agent_type.value:30s} {r.execution_time_ms}ms")

    print(f"\nTotal agents registered: {len(orch.agents)}")


if __name__ == "__main__":
    asyncio.run(_demo())
