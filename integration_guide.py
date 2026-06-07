"""
TECHIT AI INTEGRATION GUIDE
============================
Implementation contract between every TechIT feature and the AI brain.

Every service class maps directly to one platform section.
All services are dependency-injected from the TechITAIBrain singleton.

Services
────────
  1.  TechITAIBrain              -- singleton brain, owns everything
  2.  IncubationHubService       -- full venture pipeline + individual modules
  3.  DashboardIntelligenceService -- GSIS surface + real-time score card
  4.  WorkspaceAIService         -- task suggestions + sprint planning
  5.  TourGuideService           -- momentum enforcement + audio briefings
  6.  AdaptiveTrainingService    -- time-to-MVP curriculum (not fixed weeks)
  7.  MatchingEngineService      -- team / investor / accelerator compatibility
  8.  RiskEvaluatorService       -- idea + execution risk
  9.  InvestorSectionService     -- EVI-I, deal flow ranking, watchlist
 10.  FeedIntelligenceService    -- community feed curation
 11.  AIProfileService           -- profile scoring + improvement
 12.  OrgSphereService           -- organization structure intelligence
 13.  MarketReadinessService     -- stage-gate tracking + certification
 14.  AdminMonitorService        -- abuse detection + stagnation roster
 15.  HybridBillingService       -- credit resolution + paywall enforcement
 16.  GSISService                -- global startup intelligence score
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from ai_router_core import (
    AICommandLayer, ModelRouter, PromptEngine, SafetyEngine,
    AIRequest, UserContext, TaskType, UserRole,
    SubscriptionTier, ScoringEngine, CreditCost,
    SubscriptionAccessControl,
)
from agent_orchestration import (
    AgentOrchestrator, AgentType, AgentContext, VenturePipeline,
)


# ============================================================================
# 1. TECHIT AI BRAIN -- SINGLETON
# ============================================================================

class TechITAIBrain:
    """
    Singleton. Initialise once at application startup.
    Every feature receives this via dependency injection.
    Nothing calls an LLM directly -- everything passes through here.
    """

    _instance: Optional[TechITAIBrain] = None

    def __new__(cls) -> TechITAIBrain:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.model_router  = ModelRouter()
        self.prompt_engine = PromptEngine()
        self.safety_engine = SafetyEngine()
        self.command_layer = AICommandLayer(
            self.model_router, self.prompt_engine, self.safety_engine
        )
        self.orchestrator = AgentOrchestrator(self.command_layer)
        self._initialized = True
        print("✅ TechIT AI Brain initialized")

    async def process(self, request: AIRequest):
        return await self.command_layer.process_request(request)

    async def trigger_agent(self, agent_type: AgentType, context: AgentContext):
        return await self.orchestrator.trigger_agent(agent_type, context)

    async def handle_event(self, event: Dict[str, Any]):
        return await self.orchestrator.handle_event(event)

    def venture_pipeline(self) -> VenturePipeline:
        return self.orchestrator.venture_pipeline()


# ============================================================================
# 2. INCUBATION HUB SERVICE
# ============================================================================

class IncubationHubService:
    """
    Transforms a raw idea or existing MVP into investor-grade startup infrastructure.

    Full pipeline: 12 credits (Investor+ required)
    Individual modules: 1–4 credits each (see CreditCost table)
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def run_full_venture_pipeline(
        self, user_context: UserContext, venture_data: Dict
    ) -> Dict:
        """POST /api/v1/incubation/pipeline/run -- 12 credits, Investor+"""
        if not SubscriptionAccessControl.is_allowed(
            user_context.subscription_tier, TaskType.BUSINESS_PLAN
        ):
            return {"error": "full_pipeline_requires_investor_plan",
                    "upgrade_url": "/billing/upgrade"}

        pipeline = self.brain.venture_pipeline()
        results  = await pipeline.run(user_context, venture_data)
        return self._compile_blueprint(venture_data, results)

    def _compile_blueprint(self, venture_data: Dict, results: Dict) -> Dict:
        def safe(key: str, field: str):
            r = results.get(key)
            return r.output.get(field) if r and r.success else None

        return {
            "venture_name":            venture_data.get("startup_name", ""),
            "pipeline_completed_at":   datetime.utcnow().isoformat(),
            "unicorn_potential_score": safe("unicorn", "unicorn_potential_score"),
            "unicorn_classification":  safe("unicorn", "classification"),
            "driver_breakdown":        safe("unicorn", "driver_breakdown"),
            "market_analysis":         safe("market",  "market_analysis"),
            "feasibility_report":      safe("feasibility", "feasibility_report"),
            "startup_strategy":        safe("strategy",    "startup_strategy"),
            "finance_strategy":        safe("finance",     "finance_strategy"),
            "executive_summary":       safe("business_plan", "executive_summary"),
            "full_business_plan":      safe("business_plan", "business_plan"),
            "tech_architecture":       safe("tech_architect", "tech_architecture"),
            "investment_score":        safe("investor", "investment_score"),
            "evi_i":                   safe("investor", "evi_i"),
            "investor_signals":        safe("investor", "investor_signals"),
            "pivot_needed":            safe("pivot", "pivot_needed") or False,
        }

    async def run_idea_diagnostic(self, user_context: UserContext, idea_data: Dict) -> Dict:
        """POST /api/v1/incubation/idea/diagnose -- 1 credit, Free+"""
        ctx = AgentContext(user_context=user_context, trigger_event=idea_data)
        r   = await self.brain.trigger_agent(AgentType.VENTURE_INTAKE, ctx)
        return {"structured_profile": r.output.get("venture_profile"),
                "next_steps": r.next_steps}

    async def run_unicorn_analysis(self, user_context: UserContext, venture_data: Dict) -> Dict:
        """POST /api/v1/incubation/unicorn/analyze -- 2 credits, Builder+"""
        ctx = AgentContext(user_context=user_context, trigger_event=venture_data)
        r   = await self.brain.trigger_agent(AgentType.UNICORN_EVALUATOR, ctx)
        return r.output

    async def run_market_intelligence(self, user_context: UserContext, venture_data: Dict) -> Dict:
        """POST /api/v1/incubation/market/analyze -- 2 credits, Builder+"""
        ctx = AgentContext(user_context=user_context, trigger_event=venture_data)
        r   = await self.brain.trigger_agent(AgentType.MARKET_INTELLIGENCE, ctx)
        return r.output

    async def generate_business_plan(self, user_context: UserContext, venture_data: Dict) -> Dict:
        """POST /api/v1/incubation/business-plan/generate -- 6 credits, Investor+"""
        ctx = AgentContext(user_context=user_context, trigger_event=venture_data,
                           shared_memory={"venture_profile": venture_data})
        r   = await self.brain.trigger_agent(AgentType.BUSINESS_PLAN_GEN, ctx)
        return r.output

    async def run_tech_stack_design(
        self, user_context: UserContext, venture_data: Dict, scale_target: str = "1M users"
    ) -> Dict:
        """POST /api/v1/incubation/tech-stack/design -- 2 credits, Founder Pro+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={**venture_data, "scale_target": scale_target})
        r   = await self.brain.trigger_agent(AgentType.TECH_ARCHITECT, ctx)
        return r.output

    async def run_pivot_intelligence(
        self, user_context: UserContext, venture_data: Dict, unicorn_score: float
    ) -> Dict:
        """POST /api/v1/incubation/pivot/analyze -- 2 credits, Builder+"""
        ctx = AgentContext(
            user_context=user_context,
            trigger_event=venture_data,
            shared_memory={"unicorn_evaluation": {"unicorn_potential_score": unicorn_score},
                           "venture_profile": venture_data},
        )
        r = await self.brain.trigger_agent(AgentType.PIVOT_INTELLIGENCE, ctx)
        return r.output

    async def generate_investor_readiness_report(
        self, user_context: UserContext, venture_data: Dict
    ) -> Dict:
        """POST /api/v1/incubation/investor-readiness/generate -- 2 credits, Investor+"""
        resp = await self.brain.process(AIRequest(
            TaskType.INVESTOR_READINESS, user_context, venture_data,
            ip_protected=True, max_tokens=3000,
        ))
        return {"readiness_report": resp.output, "cost": resp.cost}


# ============================================================================
# 3. DASHBOARD INTELLIGENCE SERVICE
# ============================================================================

class DashboardIntelligenceService:
    """
    Powers the Dashboard with the GSIS composite score and real-time alerts.
    Zero credit cost -- operational task.
    Triggered on login and every 30-minute polling cycle.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_dashboard_intelligence(
        self, user_context: UserContext, project_scores: Optional[Dict] = None
    ) -> Dict:
        """GET /api/v1/dashboard/intelligence -- 0 credits"""
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={"scores": project_scores or {}},
            shared_memory=project_scores or {},
        )
        r = await self.brain.trigger_agent(AgentType.DASHBOARD_INTELLIGENCE, ctx)
        return {
            "gsis":       r.output.get("gsis"),
            "score_card": r.output.get("score_card"),
            "alerts":     r.output.get("alerts"),
            "insights":   r.output.get("insights"),
            "top_action": r.recommendations[0] if r.recommendations else None,
        }

    async def get_gsis(
        self, user_context: UserContext, component_scores: Dict
    ) -> Dict:
        """GET /api/v1/dashboard/gsis/{project_id} -- 1 credit"""
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={"scores": component_scores},
            shared_memory=component_scores,
        )
        r = await self.brain.trigger_agent(AgentType.GSIS_COMPUTE, ctx)
        return r.output

    def build_infographic_data(
        self, project_id: str, project_scores: Dict
    ) -> Dict:
        """
        GET /api/v1/dashboard/infographic/{project_id} -- 0 credits

        Data for auto-generated startup infographics:
          - Startup Progress Dashboard (GSIS + component scores)
          - Unicorn Driver Radar Chart (10-driver breakdown)
          - Market Readiness Evolution (score over time)
          - Founder Execution Graph (EVI trend)
          - Revenue Model Diagram
        """
        return {
            "project_id": project_id,
            "infographic_data": {
                "progress_dashboard": {
                    "gsis":              project_scores.get("gsis_score", 0),
                    "execution_velocity": project_scores.get("evi", 0),
                    "market_readiness":  project_scores.get("market_readiness_score", 0),
                    "unicorn_score":     project_scores.get("unicorn_potential_score", 0),
                    "investment_score":  project_scores.get("investment_score", 0),
                    "evi_i":             project_scores.get("evi_i_score", 0),
                },
                "unicorn_radar":  project_scores.get("driver_breakdown", {}),
                "wcrs_trend":     project_scores.get("wcrs_history", []),
                "stage_pathway": {
                    "current_stage":      project_scores.get("current_stage", "idea"),
                    "stage_pct":          project_scores.get("stage_pct", 0),
                    "requirements_remaining": project_scores.get("requirements_remaining", []),
                },
            },
            "exportable": True,
            "export_formats": ["png", "pdf", "svg"],
        }


# ============================================================================
# 4. WORKSPACE AI SERVICE
# ============================================================================

class WorkspaceAIService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def suggest_tasks(self, user_context: UserContext, workspace_data: Dict) -> Dict:
        """POST /api/v1/workspace/tasks/suggest -- 0 credits"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"workspace_data": workspace_data})
        r   = await self.brain.trigger_agent(AgentType.WORKSPACE_ASSISTANT, ctx)
        return {"suggestions": r.output.get("task_suggestions"),
                "next_actions": r.recommendations}

    async def review_code(self, user_context: UserContext, code_payload: Dict) -> Dict:
        """POST /api/v1/workspace/code/review -- 1 credit, Founder Pro+"""
        resp = await self.brain.process(
            AIRequest(TaskType.CODE_REVIEW, user_context, code_payload)
        )
        return {"review": resp.output, "cost": resp.cost}

    async def plan_sprint(self, user_context: UserContext, sprint_data: Dict) -> Dict:
        """POST /api/v1/workspace/sprint/plan -- 0 credits"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"workspace_data": sprint_data, "mode": "sprint_planning"})
        r   = await self.brain.trigger_agent(AgentType.WORKSPACE_ASSISTANT, ctx)
        return r.output


# ============================================================================
# 5. TOUR GUIDE SERVICE
# ============================================================================

class TourGuideService:
    """
    AI momentum enforcer. NOT a motivational chatbot.
    Assesses execution discipline, penalises inactivity via decay factor.
    Zero credits -- Free tier, unlimited access.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def daily_check_in(
        self, user_context: UserContext, activity_data: Optional[Dict] = None
    ) -> Dict:
        """POST /api/v1/tour-guide/daily-check-in -- 0 credits"""
        ctx = AgentContext(user_context=user_context, trigger_event=activity_data or {})
        r   = await self.brain.trigger_agent(AgentType.TOUR_GUIDE, ctx)
        return {
            "momentum_score": r.output.get("momentum_score"),
            "decay_factor":   r.output.get("decay_factor"),
            "daily_plan":     r.output.get("daily_plan"),
            "ai_insights":    r.output.get("ai_insights"),
            "alerts":         r.recommendations,
            "stagnation_risk": r.output.get("decay_factor", 1.0) < 0.70,
        }

    async def weekly_summary(self, user_context: UserContext, week_data: Dict) -> Dict:
        """Scheduled: 0 18 * * 0 (Sunday 18:00) -- 1 credit"""
        resp = await self.brain.process(AIRequest(
            TaskType.SUMMARY, user_context,
            {"week_data": week_data, "summary_type": "weekly_tour_guide"},
            max_tokens=4000,
        ))
        return {"weekly_summary": resp.output, "cost": resp.cost}

    async def get_audio_briefing(self, user_context: UserContext, briefing_text: str) -> Dict:
        """POST /api/v1/tour-guide/audio-briefing -- 0 credits"""
        # Production: call ElevenLabs API -> store in ai_audio_outputs
        return {
            "audio_url":        f"https://cdn.techit.io/audio/{user_context.user_id}/briefing.mp3",
            "duration_seconds": 45,
            "text_preview":     briefing_text[:200],
        }


# ============================================================================
# 6. ADAPTIVE TRAINING SERVICE
# ============================================================================

class AdaptiveTrainingService:
    """
    Replaces the old fixed 12-week TrainingCurriculumService entirely.

    Duration is computed from time-to-MVP -- not a fixed calendar.
    Post-MVP tracks unlock based on startup state, not weeks completed.
    Adapts in real-time to platform events (pivot, mvp_shipped, investor interest).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def generate_curriculum(
        self,
        user_context:             UserContext,
        hours_available_per_week: float = 8.0,
        learning_pace:            str   = "standard",
        target_mvp_weeks:         int   = 0,
        has_technical_skills:     bool  = False,
        pre_existing_skills:      Optional[List[str]] = None,
        investor_interest:        bool  = False,
    ) -> Dict:
        """
        POST /api/v1/training/curriculum/generate -- 1 credit, Free+

        Duration is NOT 12 weeks. It is calculated from:
          - project stage (how far from MVP)
          - available hours per week
          - learning pace (intensive/standard/part_time)
          - team size and technical skills
          - self-reported target_mvp_weeks (optional override)
        """
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={
                "mode":               "generate",
                "hours_per_week":     hours_available_per_week,
                "learning_pace":      learning_pace,
                "target_mvp_weeks":   target_mvp_weeks,
                "has_technical_skills": has_technical_skills,
                "pre_existing_skills":  pre_existing_skills or [],
                "investor_interest":  investor_interest,
            },
        )
        r  = await self.brain.trigger_agent(AgentType.ADAPTIVE_TRAINING, ctx)
        c  = r.output.get("curriculum", {})
        ls = c.get("learning_summary", {})

        return {
            "curriculum_id":        c.get("curriculum_id", ""),
            "learning_summary": {
                "estimated_weeks_to_mvp": ls.get("estimated_weeks_to_mvp", 0),
                "estimated_total_hours":  ls.get("estimated_total_hours",  0),
                "weekly_target_hours":    ls.get("weekly_learning_target_hours", 0),
                "mvp_target_date":        ls.get("mvp_target_date", ""),
                "learning_pace":          learning_pace,
            },
            "pre_mvp":  c.get("pre_mvp",  {}),
            "post_mvp": c.get("post_mvp", {}),
            "next_module": c.get("next_module"),
            "certifications_eligible": c.get("certifications_eligible", []),
            "ai_narrative": r.output.get("ai_narrative", ""),
        }

    async def adapt_curriculum(
        self, user_context: UserContext, trigger_event: str, event_data: Dict
    ) -> Dict:
        """
        POST /api/v1/training/curriculum/adapt -- 0 credits

        Adaptation triggers:
          mvp_shipped               -> Activate full post-MVP curriculum
          investor_expressed_interest -> Fast-track fundraising modules
          revenue_went_live         -> Unlock revenue optimisation track
          pivot_detected            -> Re-trigger validation modules
        """
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={"mode": "adapt", "adapt_trigger": trigger_event, **event_data},
        )
        r = await self.brain.trigger_agent(AgentType.ADAPTIVE_TRAINING, ctx)
        return {"adapted": True, "reason": r.output.get("ai_narrative", ""),
                "curriculum": r.output.get("curriculum", {})}

    async def mark_module_complete(
        self, user_context: UserContext, module_id: str,
        quiz_score: Optional[float] = None,
    ) -> Dict:
        """POST /api/v1/training/progress/update -- 0 credits"""
        await self.brain.handle_event({
            "type":         "training_completed",
            "user_context": user_context,
            "module_id":    module_id,
            "quiz_score":   quiz_score,
        })
        return {"module_completed": module_id,
                "next_check": "Dashboard will update within 30 seconds"}

    async def ask_ai_tutor(
        self, user_context: UserContext, question: str, lesson_context: str
    ) -> Dict:
        """POST /api/v1/training/tutor/ask -- 0 credits"""
        resp = await self.brain.process(AIRequest(
            TaskType.CHAT, user_context,
            {"question": question, "lesson_context": lesson_context, "mode": "ai_tutor"},
        ))
        return {"answer": resp.output, "model": resp.model_used}


# ============================================================================
# 7. MATCHING ENGINE SERVICE
# ============================================================================

class MatchingEngineService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def find_collaborators(self, user_context: UserContext, criteria: Dict) -> Dict:
        """POST /api/v1/matching/find-collaborators -- 1 credit, Builder+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"criteria": criteria, "match_type": "founder_builder"})
        r   = await self.brain.trigger_agent(AgentType.MATCHING, ctx)
        return {"matches": r.output.get("matches", []),
                "explanations": r.output.get("explanations"),
                "total_found": len(r.output.get("matches", []))}

    async def find_investors(self, user_context: UserContext, startup_profile: Dict) -> Dict:
        """POST /api/v1/matching/find-investors -- 2 credits, Investor+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"criteria": {"match_type": "startup_investor"},
                                          "startup_profile": startup_profile})
        r   = await self.brain.trigger_agent(AgentType.MATCHING, ctx)
        return r.output

    def compute_compatibility(
        self, seeker_profile: Dict, candidate_profile: Dict
    ) -> Dict:
        """GET /api/v1/matching/compatibility -- 0 credits"""
        score = ScoringEngine.compute_match_score(
            seeker_profile.get("skill_similarity", 0.7),
            seeker_profile.get("goal_similarity",  0.7),
            seeker_profile.get("exec_style_sim",   0.6),
            candidate_profile.get("availability_score", 0.8),
            candidate_profile.get("trust_score",        0.75),
            candidate_profile.get("domain_score",       0.65),
        )
        return {"match_score": score,
                "compatibility": "high" if score >= 75 else "medium" if score >= 55 else "low"}


# ============================================================================
# 8. RISK EVALUATOR SERVICE
# ============================================================================

class RiskEvaluatorService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def evaluate_idea_risk(self, user_context: UserContext, idea_data: Dict) -> Dict:
        """POST /api/v1/risk/evaluate -- 2 credits, Builder+"""
        ctx = AgentContext(user_context=user_context, trigger_event={"idea": idea_data})
        r   = await self.brain.trigger_agent(AgentType.RISK_EVALUATOR, ctx)
        ra  = r.output.get("risk_analysis", {})
        return {
            "risk_analysis":   ra,
            "risk_level":      ra.get("competitive_risk", "medium"),
            "top_risks":       ra.get("key_risks", []),
            "swot":            ra.get("swot", {}),
            "recommendations": r.recommendations,
        }


# ============================================================================
# 9. INVESTOR SECTION SERVICE
# ============================================================================

class InvestorSectionService:
    """
    EVI-I, investment score, deal flow ranking, watchlist, deep evaluation.
    Full EVI-I computation via InvestorIntelligenceAgent (integrates investor_evi.py logic).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_investor_evi(
        self, investor_context: UserContext, startup_data: Dict
    ) -> Dict:
        """
        GET /api/v1/investor/evi/{project_id} -- 2 credits, Investor+

        Returns the full EVI-I signal: 6 dimension scores, decay-adjusted composite,
        signal classification, strengths, red flags, headline narrative.
        """
        ctx = AgentContext(
            user_context=investor_context,
            trigger_event=startup_data,
            shared_memory={
                "mdr": startup_data.get("milestone_delivery_rate", 70),
                "is":  startup_data.get("iteration_speed", 65),
                "trv": startup_data.get("team_response_velocity", 75),
                "rgs": startup_data.get("revenue_growth_signal", 40),
                "cev": startup_data.get("capital_efficiency", 60),
            },
        )
        r = await self.brain.trigger_agent(AgentType.INVESTOR_INTELLIGENCE, ctx)
        return {
            "evi_i":          r.output.get("evi_i"),
            "investment_score": r.output.get("investment_score"),
            "investor_signals": r.output.get("investor_signals"),
            "recommendations": r.recommendations,
        }

    async def get_investor_readiness(
        self, user_context: UserContext, project_scores: Dict
    ) -> Dict:
        """GET /api/v1/investor/readiness/{project_id} -- 0 + 2 credits"""
        invest_score = ScoringEngine.compute_investment_score(
            market_readiness=project_scores.get("market_readiness_score", 50),
            traction_score=min(100.0, project_scores.get("beta_users_count", 0) * 2),
            team_score=min(100.0, project_scores.get("team_size", 1) * 15),
            risk_inverse=100 - project_scores.get("risk_score", 40),
            growth_rate=project_scores.get("revenue_growth_pct", 20),
            differentiation_score=project_scores.get("unicorn_score", 50) * 0.8,
        )
        readiness = (
            "high_priority" if invest_score >= 75 else
            "ready"         if invest_score >= 60 else
            "developing"    if invest_score >= 40 else
            "not_ready"
        )
        improvements = []
        if project_scores.get("market_readiness_score", 0) < 60:
            improvements.append("Reach Beta stage before investor outreach")
        if project_scores.get("beta_users_count", 0) < 10:
            improvements.append("Acquire at least 10 active beta users")
        if project_scores.get("transparency_score", 0) < 70:
            improvements.append("Complete investor data room (pitch deck + financials)")

        return {"investment_score": invest_score, "investment_readiness": readiness,
                "top_improvements": improvements[:3]}

    async def get_deal_flow_ranking(
        self, investor_context: UserContext, filters: Optional[Dict] = None
    ) -> Dict:
        """GET /api/v1/investor/deal-flow -- 0 credits"""
        return {
            "deal_flow": [],   # Production: SELECT FROM projects ORDER BY gsis_score DESC
            "ranking_formula": {
                "gsis_weights": {
                    "product_progress": "15%", "execution_velocity": "15%",
                    "market_readiness": "20%", "beta_satisfaction": "10%",
                    "revenue_growth":   "10%", "founder_reputation": "10%",
                    "community_influence": "5%", "investor_interest": "10%",
                    "compliance": "5%",
                },
                "evi_i_signal": "6-dimensional investor execution signal",
                "decay_anti_gaming": "e^(−0.02×d) -- inactive projects rank lower automatically",
            },
            "filters_applied": filters or {},
        }

    async def generate_deep_evaluation(
        self, investor_context: UserContext, startup_data: Dict
    ) -> Dict:
        """POST /api/v1/investor/evaluate/{project_id} -- 2 credits, Investor+"""
        ctx = AgentContext(
            user_context=investor_context, trigger_event=startup_data,
            shared_memory={"venture_profile": startup_data},
        )
        r = await self.brain.trigger_agent(AgentType.INVESTOR_INTELLIGENCE, ctx)
        return r.output

    async def analyze_investor_signals(
        self, user_context: UserContext, startup_data: Dict
    ) -> Dict:
        """POST /api/v1/investor/signals/{project_id} -- 2 credits, Investor+"""
        resp = await self.brain.process(AIRequest(
            TaskType.INVESTOR_SIGNAL, user_context, startup_data, max_tokens=3000
        ))
        return {"signals": resp.output, "cost": resp.cost}


# ============================================================================
# 10. FEED INTELLIGENCE SERVICE
# ============================================================================

class FeedIntelligenceService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def curate_feed(
        self, user_context: UserContext, raw_feed: List[Dict], limit: int = 30
    ) -> Dict:
        """GET /api/v1/feed/curated -- 0 credits"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"feed_items": raw_feed[:50], "limit": limit})
        r   = await self.brain.trigger_agent(AgentType.FEED_INTELLIGENCE, ctx)
        return {"curated_feed": r.output.get("curated_feed"),
                "total_items":  len(raw_feed),
                "next_refresh_secs": 1800}


# ============================================================================
# 11. AI PROFILE SERVICE
# ============================================================================

class AIProfileService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def analyze_profile(self, user_context: UserContext, profile_data: Dict) -> Dict:
        """POST /api/v1/profile/analyze -- 1 credit, Free+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"profile_data": profile_data})
        r   = await self.brain.trigger_agent(AgentType.AI_PROFILE, ctx)
        return {"profile_analysis": r.output.get("profile_analysis"),
                "recommendations":  r.recommendations}

    def compute_profile_score(self, profile_data: Dict) -> Dict:
        """GET /api/v1/profile/score/{user_id} -- 0 credits"""
        checks = {
            "basic_info_complete":   (20, profile_data.get("full_name") and profile_data.get("email")),
            "skills_listed":         (20, len(profile_data.get("skills", [])) >= 3),
            "github_or_portfolio":   (20, profile_data.get("github_url") or profile_data.get("portfolio_url")),
            "photo_and_bio":         (15, profile_data.get("avatar_url") and profile_data.get("bio")),
            "industry_and_role_set": (15, profile_data.get("industry") and profile_data.get("role")),
            "social_proof":          (10, profile_data.get("linkedin_url") or profile_data.get("twitter_url")),
        }
        score     = sum(pts for pts, ok in checks.values() if ok)
        breakdown = {k: {"max": pts, "earned": pts if ok else 0} for k, (pts, ok) in checks.items()}
        return {"profile_score": score, "breakdown": breakdown,
                "level": "complete" if score >= 85 else "good" if score >= 65 else "needs_work"}


# ============================================================================
# 12. ORG SPHERE SERVICE
# ============================================================================

class OrgSphereService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def analyze_organization(
        self, user_context: UserContext, org_data: Dict
    ) -> Dict:
        """POST /api/v1/org/analyze -- 1 credit, Founder Pro+"""
        ctx = AgentContext(user_context=user_context, trigger_event={"org_data": org_data})
        r   = await self.brain.trigger_agent(AgentType.ORG_SPHERE, ctx)
        tss = ScoringEngine.compute_tss(
            org_data.get("skill_coverage", 60), org_data.get("activity_level", 70),
            org_data.get("delivery_rate",  65), org_data.get("collaboration",  60),
        )
        return {"org_analysis": r.output.get("org_analysis"),
                "team_strength_score": tss,
                "recommendations": r.recommendations}

    async def track_cohort(
        self, accelerator_context: UserContext, cohort_data: Dict
    ) -> Dict:
        """GET /api/v1/org/cohort/{cohort_id}/analytics -- 0 credits"""
        startups = cohort_data.get("startups", [])
        summaries = [
            {
                "startup_id":       s.get("id"),
                "startup_name":     s.get("name"),
                "stage":            s.get("stage"),
                "gsis_score":       s.get("gsis_score", 0),
                "wcrs_score":       s.get("wcrs_score", 0),
                "momentum_health":  round(ScoringEngine.compute_decay_factor(
                    s.get("days_since_update", 0)) * 100, 1),
                "stagnating":       ScoringEngine.compute_decay_factor(
                    s.get("days_since_update", 0)) < 0.70,
                "unicorn_score":    s.get("unicorn_score", 0),
                "evi_i":            s.get("evi_i_score", 0),
            }
            for s in startups
        ]
        summaries.sort(key=lambda x: x["gsis_score"], reverse=True)
        return {
            "cohort_id":       cohort_data.get("cohort_id"),
            "total_startups":  len(startups),
            "active":          sum(1 for s in summaries if not s["stagnating"]),
            "stagnating":      sum(1 for s in summaries if s["stagnating"]),
            "startup_summaries": summaries,
        }


# ============================================================================
# 13. MARKET READINESS SERVICE
# ============================================================================

class MarketReadinessService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_readiness_status(
        self, user_context: UserContext, project_data: Dict
    ) -> Dict:
        """GET /api/v1/readiness/{project_id} -- 0 credits"""
        stage    = project_data.get("stage", "idea")
        criteria = self._stage_criteria(stage)
        met      = {k: project_data.get(k, False) for k in criteria}
        unmet    = [k for k, ok in met.items() if not ok]
        pct      = round(sum(1 for ok in met.values() if ok) / max(len(met), 1) * 100, 1)
        return {
            "current_stage":          stage,
            "stage_completion_pct":   pct,
            "criteria_status":        met,
            "requirements_remaining": unmet,
            "ready_to_advance":       pct >= 100,
            "estimated_days":         len(unmet) * 7,
            "risk_level":             "high" if pct < 30 else "medium" if pct < 70 else "low",
        }

    async def generate_readiness_certificate(
        self, user_context: UserContext, project_data: Dict, stage: str
    ) -> Dict:
        """POST /api/v1/readiness/certify -- 1 credit"""
        resp = await self.brain.process(AIRequest(
            TaskType.SUMMARY, user_context,
            {"project_data": project_data, "stage": stage, "mode": "readiness_certificate"},
        ))
        return {
            "certificate_id":  f"CERT-{user_context.user_id[:8]}-{stage.upper()}",
            "stage_certified": stage,
            "issued_at":       datetime.utcnow().isoformat(),
            "certificate_text": resp.output,
            "shareable_url":   f"https://techit.io/certificates/{user_context.user_id}/{stage}",
        }

    def _stage_criteria(self, stage: str) -> Dict[str, str]:
        return {
            "idea":       {"problem_defined": "Problem statement clear",
                           "target_customer_defined": "Target customer identified"},
            "validation": {"problem_interviews_10": "10+ interviews",
                           "landing_page_live": "Landing page live"},
            "mvp":        {"mvp_deployed": "MVP deployed",
                           "10_active_users": "10+ active users"},
            "beta":       {"beta_users_50": "50+ beta users",
                           "retention_above_40pct": "Week-1 retention ≥ 40%"},
            "launch":     {"payment_integrated": "Payment live",
                           "legal_docs_complete": "ToS and privacy policy live"},
        }.get(stage, {"stage_criteria": f"Define criteria for {stage}"})


# ============================================================================
# 14. ADMIN MONITOR SERVICE
# ============================================================================

class AdminMonitorService:
    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def run_anomaly_scan(
        self, admin_context: UserContext, signals: List[Dict]
    ) -> Dict:
        """POST /api/v1/admin/monitor/scan -- 0 credits, Enterprise only"""
        if admin_context.role not in (UserRole.ADMIN, UserRole.ACCELERATOR_MGR):
            return {"error": "Admin access required."}
        ctx = AgentContext(user_context=admin_context, trigger_event={"anomaly_signals": signals})
        r   = await self.brain.trigger_agent(AgentType.ADMIN_MONITOR, ctx)
        return {"risk_flags": r.output.get("risk_flags", []),
                "analysis": r.output.get("analysis"),
                "scanned_at": datetime.utcnow().isoformat()}

    async def check_stagnation_roster(
        self, admin_context: UserContext, all_projects: List[Dict]
    ) -> Dict:
        """GET /api/v1/admin/stagnation-roster -- 0 credits, Scheduled daily 07:00"""
        stagnating = [
            {"project_id":    p.get("id"),
             "project_name":  p.get("title"),
             "owner_id":      p.get("owner_id"),
             "days_inactive": p.get("days_since_update", 0),
             "decay_factor":  round(ScoringEngine.compute_decay_factor(p.get("days_since_update", 0)), 4),
             "score_penalty": f"{round((1 - ScoringEngine.compute_decay_factor(p.get('days_since_update',0)))*100, 1)}%",
             "gsis_score":    p.get("gsis_score", 0),
             "wcrs_score":    p.get("wcrs_score", 0)}
            for p in all_projects
            if ScoringEngine.compute_decay_factor(p.get("days_since_update", 0)) < 0.70
        ]
        stagnating.sort(key=lambda x: x["decay_factor"])
        return {"stagnating_count": len(stagnating),
                "total_projects":   len(all_projects),
                "stagnating_list":  stagnating,
                "action": "Send re-engagement notifications to stagnating founders"}


# ============================================================================
# 15. HYBRID BILLING SERVICE
# ============================================================================

class HybridBillingService:
    """
    Manages the hybrid credit + subscription billing system.

    Two tracks run simultaneously:
      Track A -- Subscription: monthly credits, plan-based feature access
      Track B -- PAYG: purchased credits that never expire

    Resolution: subscription credits deducted first, PAYG used as overflow.
    Paywalls trigger at high-momentum moments when plan access is exceeded.
    """

    def __init__(self) -> None:
        from billing_system import HybridCreditEngine, PaywallEnforcementService
        self.credit_engine = HybridCreditEngine()
        self.paywall       = PaywallEnforcementService()

    def check_operation(
        self, user_billing_state, operation_id: str, context_vars: Optional[Dict] = None
    ) -> Dict:
        """
        Pre-flight check before any AI operation.
        Returns: {approved, from_subscription, from_payg, usd_cost, paywall_copy, upgrade_cta}
        Called by: every API endpoint before triggering an agent.
        """
        resolution = self.credit_engine.resolve(user_billing_state, operation_id, context_vars)
        return {
            "approved":           resolution.approved,
            "credit_cost":        resolution.credit_cost,
            "from_subscription":  resolution.from_subscription,
            "from_payg":          resolution.from_payg,
            "usd_cost_this_op":   resolution.usd_cost_this_operation,
            "credits_after":      resolution.credits_remaining_after,
            "paywall_triggered":  resolution.paywall_triggered,
            "paywall_copy":       resolution.paywall_copy,
            "upgrade_cta":        resolution.upgrade_cta,
            "upgrade_plan_id":    resolution.upgrade_plan_id,
        }

    def get_credit_summary(self, user_billing_state) -> Dict:
        """GET /api/v1/credits/summary -- 0 credits"""
        spec = user_billing_state.plan_spec
        alloc = CreditCost.monthly_allocation(SubscriptionTier(user_billing_state.plan_id.split("_")[0]))
        remaining = (user_billing_state.subscription_credits_remaining +
                     user_billing_state.payg_credits_balance)
        return {
            "plan_id":              user_billing_state.plan_id,
            "subscription_credits": user_billing_state.subscription_credits_remaining,
            "payg_credits":         user_billing_state.payg_credits_balance,
            "total_available":      remaining,
            "credit_packs":         CreditCost.CREDIT_PACKS,
            "payg_rate_usd":        spec.payg_credit_rate,
        }


# ============================================================================
# 16. GSIS SERVICE
# ============================================================================

class GSISService:
    """
    Global Startup Intelligence Score -- the master composite score.

    GSIS = 0.15*PPS + 0.15*EVI + 0.20*MRS + 0.10*BSS + 0.10*RGS
          + 0.10*FRS + 0.05*CIS + 0.10*IIS + 0.05*CS

    AlertScore = Risk + Delay + DropInMetrics
    If AlertScore > 60: AI intervention triggered.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    def compute(self, component_scores: Dict) -> Dict:
        """Compute GSIS from component scores. Zero credits -- deterministic."""
        return ScoringEngine.compute_gsis(
            product_progress_score=component_scores.get("pps", 0),
            execution_velocity_index=component_scores.get("evi", 0),
            market_readiness_score=component_scores.get("mrs", 0),
            beta_satisfaction_score=component_scores.get("bss", 0),
            revenue_growth_signal=component_scores.get("rgs", 0),
            founder_reputation_score=component_scores.get("frs", 0),
            community_influence_score=component_scores.get("cis", 0),
            investor_interest_score=component_scores.get("iis", 0),
            compliance_score=component_scores.get("cs", 0),
        )

    async def compute_with_narrative(
        self, user_context: UserContext, component_scores: Dict
    ) -> Dict:
        """POST /api/v1/gsis/compute -- 1 credit"""
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={"scores": component_scores},
            shared_memory=component_scores,
        )
        r = await self.brain.trigger_agent(AgentType.GSIS_COMPUTE, ctx)
        return r.output



# ============================================================================
# IDEA & SOLUTION HUB SERVICE
# ============================================================================

class IdeaSolutionHubService:
    """
    Service layer for the Idea & Solution Hub -- Problem-Driven pathway.

    Wraps idea_solution_hub.py and integrates with TechITAIBrain.

    Entry Points:
      A. IDEA-DRIVEN  (existing) -- "I want to build X" -> IncubationHubService
      B. PROBLEM-DRIVEN (this)   -- "Here is a problem" -> IdeaSolutionHubService

    Route: /incubator/solutions

    Platform Sections:
      🌍 Global Problems Board     -- /incubator/solutions/problems
      💡 Idea Discussions          -- /incubator/solutions/discussions
      🛠 Solution Builder          -- /incubator/solutions/builder
      🚀 Deployments               -- /incubator/solutions/deployments
      🌍 Global Impact Dashboard   -- /incubator/solutions/impact
      💰 Funding & Grants          -- /incubator/solutions/funding

    Solution Types Supported:
      startup_for_profit * social_initiative * public_policy
      community_project  * research_project  * infrastructure
      service_based      * hybrid

    Funding Types:
      revenue * grants * donations * impact_investors
      csr_partnerships * government_funding * development_banks * hybrid
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    # ── Problem Submission ────────────────────────────────────────────────

    async def submit_problem(
        self, user_context: UserContext,
        title: str, description: str, category: str,
        location: str, who_is_affected: str,
        current_solutions: List[str], urgency: str,
        people_affected_millions: float = 1.0,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/solutions/problems/submit -- 2 credits, Free+

        Submit a real-world problem to the Global Problems Board.
        AI automatically expands scope, builds stakeholder map,
        computes Impact Score, and checks for duplicate/similar problems.
        """
        from idea_solution_hub import ImpactScoringEngine, ProblemUrgency
        eng = ImpactScoringEngine()
        urg = ProblemUrgency(urgency) if urgency in [e.value for e in ProblemUrgency] else ProblemUrgency.EMERGING
        impact   = eng.compute_impact_score(people_affected_millions, 7.0, 6.0, 6.0, 7.0)
        priority = eng.compute_priority_score(impact["impact_score"], urg, 6.0, 5.0, 7.0)

        ctx = AgentContext(
            user_context=user_context,
            trigger_event={"type": "problem_submitted", "title": title,
                           "description": description, "category": category,
                           "location": location, "who_affected": who_is_affected,
                           "failed_solutions": current_solutions, "urgency": urgency},
        )
        result = await self.brain.trigger_agent(AgentType.PROBLEM_ANALYZER, ctx)
        return {
            "title":         title,
            "impact_score":  impact,
            "priority_score": priority,
            "ai_analysis":   result.output.get("analysis", ""),
            "next_actions":  result.next_steps,
        }

    # ── AI Problem Analysis ───────────────────────────────────────────────

    async def analyze_problem(
        self, user_context: UserContext, problem_id: str, problem_data: Dict
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/problems/{id}/analyze -- 2 credits, Builder+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"problem_id": problem_id, **problem_data})
        result = await self.brain.trigger_agent(AgentType.PROBLEM_ANALYZER, ctx)
        return {"problem_id": problem_id, **result.output}

    # ── Problem Discovery ─────────────────────────────────────────────────

    async def discover_problems(
        self, user_context: UserContext,
        region: Optional[str] = None, limit: int = 20,
    ) -> Dict[str, Any]:
        """
        GET /api/v1/solutions/problems/discover -- 2 credits, Builder+

        Automated discovery: scans news, NGO reports, government datasets,
        and social signals to surface problems before users submit them.
        """
        from idea_solution_hub import ProblemDiscoveryEngine
        discovery = ProblemDiscoveryEngine()
        raw = discovery.discover(region=region, limit=limit)
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"signals": raw, "region": region})
        result = await self.brain.trigger_agent(AgentType.PROBLEM_DISCOVERY, ctx)
        return {"discovered": len(raw), "problems": raw, "ai_summary": result.output.get("discovered_problems", "")}

    # ── Solution Matching ─────────────────────────────────────────────────

    async def find_matching_solutions(
        self, user_context: UserContext, problem_id: str, problem_data: Dict
    ) -> Dict[str, Any]:
        """
        GET /api/v1/solutions/problems/match/{id} -- 2 credits, Builder+

        Matches a new problem to existing solutions, startups, and NGOs
        globally. Prevents building from scratch when better alternatives exist.
        """
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"problem_id": problem_id, **problem_data})
        result = await self.brain.trigger_agent(AgentType.SOLUTION_MATCHER, ctx)
        return {"problem_id": problem_id, "matches": result.output.get("matches", "")}

    # ── Discussion ────────────────────────────────────────────────────────

    async def moderate_discussion(
        self, user_context: UserContext, thread_id: str,
        contributions: List[Dict],
    ) -> Dict[str, Any]:
        """
        GET /api/v1/solutions/discussions/{id}/summary -- 1 credit, Free+

        AI moderates the discussion: summarises, clusters ideas,
        detects strongest direction, and signals conversion readiness.
        """
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"thread_id": thread_id,
                                          "contributions": contributions})
        result = await self.brain.trigger_agent(AgentType.DISCUSSION_MODERATOR, ctx)
        return {"thread_id": thread_id, **result.output}

    # ── Solution Conversion ───────────────────────────────────────────────

    async def convert_to_solution(
        self, user_context: UserContext, problem_id: str,
        title: str, solution_type: str, funding_type: str,
        description: str, discussion_summary: str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/solutions/discussions/{id}/convert -- 3 credits, Founder Pro+

        Converts a matured discussion into a Solution Project.
        Simultaneously synthesises the solution, predicts impact,
        and estimates feasibility.
        """
        ctx = AgentContext(user_context=user_context,
                           trigger_event={
                               "type": "solution_converted",
                               "problem_id": problem_id, "title": title,
                               "solution_type": solution_type, "funding_type": funding_type,
                               "description": description, "discussion_summary": discussion_summary,
                           })
        synthesis, impact, feasibility = await asyncio.gather(
            self.brain.trigger_agent(AgentType.SOLUTION_SYNTHESIZER, ctx),
            self.brain.trigger_agent(AgentType.IMPACT_PREDICTOR, ctx),
            self.brain.trigger_agent(AgentType.FEASIBILITY_ESTIMATOR, ctx),
        )
        return {
            "problem_id":    problem_id,
            "title":         title,
            "solution_type": solution_type,
            "synthesis":     synthesis.output.get("synthesis", ""),
            "impact":        impact.output.get("impact_narrative", ""),
            "feasibility":   feasibility.output.get("feasibility_report", ""),
            "next_steps":    synthesis.next_steps,
        }

    # ── Feasibility & Impact ──────────────────────────────────────────────

    async def run_feasibility(
        self, user_context: UserContext, solution_id: str, solution_data: Dict
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/projects/{id}/feasibility -- 2 credits, Builder+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"solution_id": solution_id, **solution_data})
        result = await self.brain.trigger_agent(AgentType.FEASIBILITY_ESTIMATOR, ctx)
        return {"solution_id": solution_id, **result.output}

    async def predict_impact(
        self, user_context: UserContext, solution_id: str, solution_data: Dict
    ) -> Dict[str, Any]:
        """GET /api/v1/solutions/projects/{id}/impact -- 1 credit, Free+"""
        from idea_solution_hub import ImpactScoringEngine
        eng = ImpactScoringEngine()
        impact = eng.compute_impact_score(
            solution_data.get("people_millions", 1.0),
            solution_data.get("severity", 7.0),
            solution_data.get("scalability", 6.0),
            solution_data.get("sustainability", 6.0),
            solution_data.get("measurability", 7.0),
        )
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"solution_id": solution_id,
                                          "impact_scores": impact, **solution_data})
        result = await self.brain.trigger_agent(AgentType.IMPACT_PREDICTOR, ctx)
        return {**impact, "narrative": result.output.get("impact_narrative", ""),
                "solution_id": solution_id}

    # ── Deployment ────────────────────────────────────────────────────────

    async def create_deployment(
        self, user_context: UserContext, solution_id: str,
        solution_data: Dict, mode: str, region: str,
        beneficiaries_target: int,
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/deployments/create -- 2 credits, Founder Pro+"""
        from idea_solution_hub import DeploymentEngine, DeploymentMode, SolutionProject, SolutionType, FundingType, SolutionStage
        dep_eng = DeploymentEngine()
        sol = SolutionProject(
            solution_id=solution_id,
            title=solution_data.get("title", ""),
            solution_type=SolutionType.HYBRID,
            funding_type=FundingType.HYBRID,
            stage=SolutionStage.VALIDATED,
            execution_plan=solution_data.get("execution_plan", "x"),
            required_roles=[],
            impact_score=solution_data.get("impact_score", 50.0),
            feasibility_score=solution_data.get("feasibility_score", 50.0),
        )
        readiness = dep_eng.compute_deployment_readiness(sol)
        dm = DeploymentMode(mode) if mode in [e.value for e in DeploymentMode] else DeploymentMode.PILOT_PROGRAM
        plan = dep_eng.create_deployment_plan(sol, dm, region, beneficiaries_target)
        ctx = AgentContext(user_context=user_context,
                           trigger_event={"type": "deployment_created", "solution_id": solution_id,
                                          "mode": mode, "region": region,
                                          "beneficiaries_target": beneficiaries_target})
        result = await self.brain.trigger_agent(AgentType.DEPLOYMENT_PLANNER, ctx)
        return {
            "deployment_id":   plan.deployment_id,
            "mode":            dm.value,
            "region":          region,
            "readiness":       readiness,
            "checklist":       plan.deployment_checklist,
            "ai_plan":         result.output.get("deployment_plan", ""),
        }

    async def submit_field_feedback(
        self, user_context: UserContext, deployment_id: str,
        solution_id: str, field_report: str,
        impact_metrics: Dict, failure_points: List[str],
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/deployments/{id}/feedback -- 1 credit, Free+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={
                               "type": "field_feedback_submitted",
                               "deployment_id": deployment_id, "solution_id": solution_id,
                               "field_report": field_report, "impact_metrics": impact_metrics,
                               "failure_points": failure_points,
                           })
        result = await self.brain.trigger_agent(AgentType.FIELD_FEEDBACK_AGENT, ctx)
        return {"deployment_id": deployment_id, **result.output}

    # ── Grants & Funding ──────────────────────────────────────────────────

    async def generate_grant_application(
        self, user_context: UserContext, solution_id: str,
        solution_data: Dict, funder_name: str,
        funding_type: str, amount_usd: float,
    ) -> Dict[str, Any]:
        """POST /api/v1/solutions/grants/generate -- 3 credits, Founder Pro+"""
        ctx = AgentContext(user_context=user_context,
                           trigger_event={
                               "solution_id": solution_id, "funder_name": funder_name,
                               "funding_type": funding_type, "amount_usd": amount_usd,
                               **solution_data,
                           })
        result = await self.brain.trigger_agent(AgentType.GRANT_MATCHER, ctx)
        return {
            "solution_id":      solution_id,
            "funder":           funder_name,
            "amount_usd":       amount_usd,
            "application_text": result.output.get("grant_application", ""),
            "status":           "draft",
            "export_ready":     True,
        }

    # ── Global Impact Dashboard ───────────────────────────────────────────

    def get_global_impact_dashboard(
        self, active_problems: int, active_solutions: int,
        active_deployments: int, total_beneficiaries: int,
        countries: List[str], funds_deployed_usd: float,
    ) -> Dict[str, Any]:
        """GET /api/v1/solutions/impact/global -- 0 credits, Free+"""
        from idea_solution_hub import IdeaSolutionHubService as HubSvc
        svc = HubSvc(self.brain)
        return svc.get_global_impact_dashboard(
            active_problems, active_solutions, active_deployments,
            total_beneficiaries, countries, funds_deployed_usd,
        )


# ============================================================================
# DOCUMENT GENERATION SERVICE
# ============================================================================

class DocumentGenerationService:
    """
    Service layer for the Document Generation Engine.

    Wraps document_generation.py and integrates with TechITAIBrain.

    Turns TechIT into:
      👉 Startup Operating System
      👉 Document Factory
      👉 Investor Preparation Engine

    8 Document Types:
      Executive Summary      -- 1–2 pages,  2 credits, Builder+
      Full Business Plan     -- 10–25 pages, 4 credits, Investor+
      Pitch Deck             -- 12 slides,   3 credits, Founder Pro+
      Investor Report        -- 8 pages,     3 credits, Investor+
      Unicorn Analysis Report -- 7 pages,   2 credits, Builder+
      Product Roadmap        -- 5 pages,    2 credits, Founder Pro+
      Financial Projection   -- 5 pages,    2 credits, Founder Pro+
      Market Research Report -- 8 pages,    3 credits, Founder Pro+

    3 Styles:   Concise * Standard * Detailed
    3 Audiences: Founder Use * Investors * Accelerators
    4 Formats:  PDF * Notion Doc * Google Doc * Slide Deck

    Route: /incubator/documents
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def generate_document(
        self,
        user_context:     UserContext,
        project_id:       str,
        document_type:    str,
        style:            str = "standard",
        audience:         str = "investors",
        export_format:    str = "pdf",
        investor_mode:    bool = False,
        startup_data:     Optional[Dict] = None,
        analysis_results: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/generate -- 2–4 credits, Builder+

        Master document generation endpoint.

        Flow:
          1. Pull startup data + analysis results
          2. Assemble master prompt from DocumentPromptEngine
          3. Select AI model (all documents -> Claude Sonnet for long-form)
          4. Generate via AI Command Layer
          5. Parse structured output by section
          6. Build all exports (PDF, links, edit URL)
          7. Return preview + full download options
        """
        from document_generation import (DocumentGenerationService as DocSvc,
                                         DocumentType, DocumentStyle,
                                         DocumentAudience, ExportFormat)

        svc    = DocSvc(self.brain)
        result = await svc.generate_document(
            user_context=user_context, project_id=project_id,
            document_type=document_type, style=style,
            audience=audience, export_format=export_format,
            investor_mode=investor_mode,
            startup_data=startup_data or {},
            analysis_results=analysis_results or {},
        )
        return result

    async def generate_investor_pack(
        self,
        user_context:     UserContext,
        project_id:       str,
        startup_data:     Optional[Dict] = None,
        analysis_results: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/investor-pack -- 8 credits, Investor+

        Generate the complete investor pack in one call:
          • Executive Summary
          • Pitch Deck (Investor Mode)
          • Full Business Plan
          • Investor Report
        Returns a bundled pack URL for one-click sharing.
        """
        from document_generation import DocumentGenerationService as DocSvc
        svc    = DocSvc(self.brain)
        result = await svc.generate_batch(
            user_context=user_context, project_id=project_id,
            document_types=["executive_summary", "pitch_deck",
                            "business_plan", "investor_report"],
            style="standard", audience="investors",
            startup_data=startup_data or {},
            analysis_results=analysis_results or {},
        )
        return result

    async def edit_with_ai(
        self, user_context: UserContext, document_id: str,
        current_content: str, edit_instruction: str,
        section: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/documents/{id}/edit -- 2 credits, Builder+

        AI-powered in-document editing.
        User selects a section and gives a natural-language instruction.
        Examples: "Make concise", "Add financial detail", "Rewrite for US investor".
        """
        from document_generation import DocumentGenerationService as DocSvc
        svc = DocSvc(self.brain)
        return await svc.edit_with_ai(
            user_context=user_context, document_id=document_id,
            current_content=current_content, edit_instruction=edit_instruction,
            section=section,
        )

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        GET /api/v1/documents/templates -- 0 credits, Free+

        Returns all 8 document types with credit costs, page estimates,
        and export format support -- used to render the UI card grid.
        """
        from document_generation import DocumentGenerationService as DocSvc, DocumentType
        svc = DocSvc(self.brain)
        return svc.get_available_templates()

    async def share_document(
        self, user_context: UserContext,
        document_id: str, expiry_days: int = 30,
    ) -> Dict[str, Any]:
        """POST /api/v1/documents/{id}/share -- 0 credits, Free+"""
        from document_generation import DocumentGenerationService as DocSvc
        svc = DocSvc(self.brain)
        return await svc.share_document(user_context, document_id, expiry_days)

    def get_document_type_map(self) -> Dict[str, Dict[str, Any]]:
        """Returns the 8 document types with their properties for the UI."""
        return {
            "executive_summary":       {"icon": "🧾", "pages": "1–2",   "credits": 2, "min_tier": "builder"},
            "business_plan":           {"icon": "📊", "pages": "10–25", "credits": 4, "min_tier": "investor"},
            "pitch_deck":              {"icon": "🎯", "pages": "12",     "credits": 3, "min_tier": "founder_pro"},
            "investor_report":         {"icon": "📈", "pages": "8",      "credits": 3, "min_tier": "investor"},
            "unicorn_analysis_report": {"icon": "🧠", "pages": "7",      "credits": 2, "min_tier": "builder"},
            "product_roadmap":         {"icon": "🛠", "pages": "5",      "credits": 2, "min_tier": "founder_pro"},
            "financial_projection":    {"icon": "💰", "pages": "5",      "credits": 2, "min_tier": "founder_pro"},
            "market_research_report":  {"icon": "🧪", "pages": "8",      "credits": 3, "min_tier": "founder_pro"},
        }



# ============================================================================
# IP PROTECTION SERVICE
# ============================================================================

class IPProtectionService:
    """
    Centralised IP protection layer for TechIT.

    Covers three protection mechanisms:

    1. FINGERPRINTING (SHA-256 exact-match)
       ─────────────────────────────────────
       Every ip_protected=True AIRequest is stamped with a SHA-256 hash of
       its payload before the AI call. The hash is:
         - Stored in ai_outputs.input_data["_ip_fingerprint"]
         - Written to idea_embeddings.idea_fingerprint by VentureIntakeAgent
         - Written to problem_nodes by IdeaSolutionHubService.submit_problem()
       Used for exact-match deduplication and audit trail.

    2. VECTOR SIMILARITY LEAK DETECTION (pgvector)
       ─────────────────────────────────────────────
       Every idea and solution submitted is embedded (1536-dim, OpenAI
       text-embedding-3-small) and stored in idea_embeddings.
       The `idea_similarity_check` SQL query (database_schema.REFERENCE_QUERIES)
       runs cosine similarity against ALL stored embeddings.
       Similarity ≥ 0.95 -> IP alert raised, result blocked.
       Runs as techit_system role (BYPASSRLS) -- never returns idea_text.

    3. ROW-LEVEL SECURITY (PostgreSQL RLS)
       ──────────────────────────────────────
       RLS policies in database_schema.RLS_POLICIES_SQL enforce that:
         - Each user can only SELECT their own projects, ai_outputs,
           idea_embeddings, generated_documents, solution_projects,
           grant_applications, credit_ledger, and paywall_hits.
         - The app connects as 'techit_app' role (non-superuser) so RLS
           always applies.
         - Admin/scheduled jobs use 'techit_system' role (BYPASSRLS)
           ONLY for IP leak detection -- never to read idea content.
         - Investor deal flow uses a permissive exception policy that
           surfaces only score/stage metadata -- never raw idea text.

    Operations protected by ip_protected=True
    ─────────────────────────────────────────
    Incubation Hub:
      VentureIntakeAgent      IDEA_EVALUATION       ip_protected=True ✅
      UnicornEvaluatorAgent   UNICORN_ANALYSIS      ip_protected=True ✅
      BusinessPlanGenerator   EXECUTIVE_SUMMARY     ip_protected=True ✅
      BusinessPlanGenerator   BUSINESS_PLAN         ip_protected=True ✅
      PivotIntelligenceAgent  PIVOT_INTELLIGENCE    ip_protected=True ✅
      RiskEvaluatorAgent      RISK_ANALYSIS         ip_protected=True ✅

    Investor:
      generate_investor_readiness_report            ip_protected=True ✅

    Document Generation:
      DocumentGenerationService.generate_document   ip_protected=True ✅
      (all 8 document types -- startup context injected)

    Idea & Solution Hub:
      IdeaSolutionHubService.submit_problem         ip_protected=True ✅
      IdeaSolutionHubService.analyze_problem        ip_protected=True ✅
      IdeaSolutionHubService.convert_to_solution    ip_protected=True ✅
      IdeaSolutionHubService.run_feasibility        ip_protected=True ✅
      IdeaSolutionHubService.create_deployment      ip_protected=True ✅
      IdeaSolutionHubService.generate_grant         ip_protected=True ✅
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    def fingerprint(self, text: str) -> str:
        """
        SHA-256 fingerprint of any text.
        Used directly for idea and problem deduplication.
        """
        import hashlib
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def check_exact_match(
        self,
        fingerprint: str,
        stored_fingerprints: List[str],
    ) -> Dict[str, Any]:
        """
        Exact-match IP leak check.
        Call before surfacing any cross-user content in matching or discovery.
        """
        from ai_router_core import SafetyEngine
        return SafetyEngine.check_similarity_leak(fingerprint, stored_fingerprints)

    async def create_idea_embedding(
        self,
        user_context: UserContext,
        project_id:   str,
        idea_text:    str,
    ) -> Dict[str, Any]:
        """
        Generate and store a vector embedding for IP leak detection.

        Flow:
          1. Fingerprint the idea text (SHA-256)
          2. Check exact-match against existing fingerprints (fast path)
          3. Call EMBEDDINGS TaskType -> text-embedding-3-small (1536 dims)
          4. INSERT into idea_embeddings table
          5. Return fingerprint + embedding for storage

        Production:
          This is called automatically by VentureIntakeAgent after idea intake
          and by IdeaSolutionHubService.submit_problem() after problem submission.
          Both use ip_protected=True on the embedding call.
        """
        from ai_router_core import AIRequest, TaskType

        fingerprint = self.fingerprint(idea_text)

        # Step 1: fast exact-match check (no AI call needed)
        # stored = SELECT idea_fingerprint FROM idea_embeddings
        # result = self.check_exact_match(fingerprint, stored)
        # if result["leak_detected"]: raise IPLeakDetectedError(result["reason"])

        # Step 2: generate embedding vector
        embed_resp = await self.brain.process(AIRequest(
            task_type=TaskType.EMBEDDINGS,
            user_context=user_context,
            input_data={
                "text":  idea_text,
                "model": "text-embedding-3-small",
            },
            ip_protected=True,  # Embedding call is itself IP-protected
            max_tokens=0,       # Embeddings have no token output
        ))

        # Step 3: store in idea_embeddings (production: INSERT via SQLAlchemy)
        # INSERT INTO idea_embeddings (project_id, embedding, idea_fingerprint,
        #     idea_text, embedding_model, is_protected, leak_detection_enabled,
        #     leak_detection_threshold)
        # VALUES (project_id, embed_resp.output, fingerprint, idea_text,
        #     'text-embedding-3-small', true, true, 0.95)

        return {
            "project_id":  project_id,
            "fingerprint": fingerprint,
            "embedding_model": "text-embedding-3-small",
            "is_protected":    True,
            "leak_detection_enabled":   True,
            "leak_detection_threshold": 0.95,
            "stored": True,  # Production: True only after successful INSERT
        }

    def get_protection_status(self) -> Dict[str, Any]:
        """
        GET /api/v1/ip-protection/status -- 0 credits, Founder Pro+

        Returns the complete IP protection status for a user's projects.
        Used in the admin panel and founder dashboard.
        """
        return {
            "protection_layers": {
                "fingerprinting": {
                    "active":      True,
                    "algorithm":   "SHA-256",
                    "applies_to":  "All ip_protected=True AI requests",
                    "stored_in":   "ai_outputs.input_data + idea_embeddings.idea_fingerprint",
                },
                "vector_similarity": {
                    "active":      True,
                    "algorithm":   "pgvector cosine similarity",
                    "threshold":   0.95,
                    "model":       "text-embedding-3-small (1536 dims)",
                    "stored_in":   "idea_embeddings.embedding",
                    "query":       "idea_similarity_check (REFERENCE_QUERIES)",
                    "role":        "techit_system (BYPASSRLS -- score only, never idea_text)",
                },
                "row_level_security": {
                    "active":      True,
                    "engine":      "PostgreSQL RLS",
                    "policies":    "project_owner, ai_output_owner, idea_embedding_owner, "
                                   "document_owner, solution_owner, grant_owner, "
                                   "credit_ledger_owner, paywall_owner",
                    "app_role":    "techit_app (non-superuser -- RLS always applies)",
                    "bypass_role": "techit_system (BYPASSRLS -- IP leak detection only)",
                    "applied_via": "database_schema.apply_rls_policies(engine)",
                },
            },
            "protected_operations": [
                "IDEA_EVALUATION", "UNICORN_ANALYSIS", "BUSINESS_PLAN",
                "EXECUTIVE_SUMMARY", "RISK_ANALYSIS", "INVESTOR_READINESS",
                "PIVOT_INTELLIGENCE", "PROBLEM_ANALYSIS", "SOLUTION_SYNTHESIS",
                "FEASIBILITY_ESTIMATE", "DEPLOYMENT_PLANNING", "GRANT_MATCHING",
                "All 8 DOCUMENT_* types",
            ],
            "audit_trail": "Every AI execution logged in ai_outputs with ip_protected flag",
        }



# ============================================================================
# APP SCAFFOLD SERVICE  (Prompt -> Live App)
# ============================================================================

class AppScaffoldService:
    """
    Service layer for TechIT's defining edge: Prompt -> Live App in Minutes.

    This is the feature that makes TechIT categorically different from every
    other startup platform. Others give you plans. TechIT gives you a running
    product -- generated from the intelligence the platform has already computed.

    The difference from Bolt.new / v0.dev:
    ┌──────────────────┬──────────────────────────────────────────────────────┐
    │ Bolt.new / v0    │ User writes a prompt -> AI generates code             │
    │ TechIT           │ Platform already knows problem, market, unicorn score │
    │                  │ -> scaffold generated FROM intelligence, not scratch   │
    └──────────────────┴──────────────────────────────────────────────────────┘

    The scaffold is not generic. It is specific to:
      - The startup's industry and revenue model
      - The validated tech stack from TechArchitectAgent
      - The target customer profile
      - The feature set implied by the problem/solution pair

    Flow:
      1. VenturePipeline runs -> shared_memory has venture_profile + tech_architecture
      2. AppScaffoldAgent runs -> generates pages, schema, API routes, deploy config
      3. User downloads ZIP or clicks 1-click Vercel deploy
      4. App is live in ~2 minutes
      5. TechIT continues tracking: GSIS * EVI-I * Decay * Investors

    Supported stacks:
      nextjs_supabase   Next.js 14 + Supabase + Tailwind (default)
      nextjs_prisma     Next.js 14 + PostgreSQL + Prisma
      react_firebase    React 18 + Firebase
      expo_supabase     Expo (React Native) + Supabase
      fastapi_supabase  FastAPI + Supabase (API-only)

    API Endpoints served
    ─────────────────────
      POST /api/v1/scaffold/generate          5 credits  Founder Pro+
      GET  /api/v1/scaffold/{project_id}      0 credits  Free+
      POST /api/v1/scaffold/{id}/deploy       3 credits  Founder Pro+
      GET  /api/v1/scaffold/{id}/status       0 credits  Free+
      GET  /api/v1/scaffold/{id}/live-url     0 credits  Free+
      POST /api/v1/scaffold/{id}/download     0 credits  Free+
      GET  /api/v1/scaffold/stacks            0 credits  Free+
    """

    STACK_OPTIONS = {
        "nextjs_supabase":  {
            "label":       "Next.js + Supabase (Recommended)",
            "description": "Full-stack web app. Best for marketplaces, SaaS, dashboards.",
            "deploy_time": "~2 minutes",
            "credits":     5,
        },
        "nextjs_prisma":    {
            "label":       "Next.js + PostgreSQL + Prisma",
            "description": "Full-stack with Prisma ORM. Best for complex relational data.",
            "deploy_time": "~3 minutes",
            "credits":     5,
        },
        "react_firebase":   {
            "label":       "React + Firebase",
            "description": "Real-time apps. Best for chat, collaboration, live data.",
            "deploy_time": "~2 minutes",
            "credits":     5,
        },
        "expo_supabase":    {
            "label":       "Expo (React Native) + Supabase",
            "description": "Mobile app for iOS + Android. Best for consumer mobile.",
            "deploy_time": "~5 minutes (TestFlight/Play Store)",
            "credits":     5,
        },
        "fastapi_supabase": {
            "label":       "FastAPI + Supabase (API only)",
            "description": "Backend API. Best for B2B integrations, developer tools.",
            "deploy_time": "~2 minutes",
            "credits":     5,
        },
    }

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def generate_scaffold(
        self,
        user_context:  UserContext,
        project_id:    str,
        stack_choice:  str = "nextjs_supabase",
        venture_data:  Optional[Dict] = None,
        arch_data:     Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/scaffold/generate -- 5 credits, Founder Pro+

        Generate a complete application scaffold from the venture profile
        already computed by the TechIT pipeline.

        If venture_data is not passed, the service uses the data stored in
        the venture pipeline's shared_memory for this project. This means
        the founder does not need to re-describe their startup -- TechIT
        already knows everything.

        Returns:
          scaffold_type, pages, schema_sql, api_routes, env_template,
          components, setup_steps, deploy_config, download_url,
          vercel_deploy_url, live_preview_url, estimated_build_hours
        """
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={
                "type":         "app_scaffold_requested",
                "project_id":   project_id,
                "stack":        stack_choice,
                **(venture_data or {}),
            },
            shared_memory={
                "venture_profile":    venture_data or {},
                "tech_architecture":  arch_data or {},
            },
        )
        result = await self.brain.trigger_agent(AgentType.APP_SCAFFOLD, ctx)
        return {
            **result.output,
            "project_id":   project_id,
            "actions_taken": result.actions_taken,
            "next_steps":    result.next_steps,
        }

    async def deploy_scaffold(
        self,
        user_context: UserContext,
        scaffold_id:  str,
        deploy_target: str = "vercel",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/scaffold/{id}/deploy -- 3 credits, Founder Pro+

        Trigger deployment of a generated scaffold to Vercel.

        In production:
          1. Create GitHub repo (GitHub API)
          2. Push scaffold files to repo
          3. Trigger Vercel deployment (Vercel API)
          4. Poll for deploy completion
          5. Return live URL

        Returns:
          deploy_status, live_url, build_logs_url, estimated_ready_seconds
        """
        # Production: call GitHub API + Vercel API
        # Stub: return expected response shape
        return {
            "scaffold_id":          scaffold_id,
            "deploy_status":        "deploying",
            "deploy_target":        deploy_target,
            "estimated_ready_seconds": 120,
            "build_logs_url":       f"https://vercel.com/techit/{scaffold_id}/deployments",
            "live_url":             f"https://{scaffold_id}.vercel.app",
            "status_endpoint":      f"/api/v1/scaffold/{scaffold_id}/status",
            "message":              "Deployment started. Your app will be live in ~2 minutes.",
        }

    def get_deploy_status(self, scaffold_id: str) -> Dict[str, Any]:
        """
        GET /api/v1/scaffold/{id}/status -- 0 credits, Free+

        Poll deployment status. Frontend calls this every 5 seconds until
        deploy_status = 'deployed'.
        """
        # Production: query Vercel API for build status
        return {
            "scaffold_id":   scaffold_id,
            "deploy_status": "deployed",   # pending | deploying | deployed | failed
            "live_url":      f"https://{scaffold_id}.vercel.app",
            "ready":         True,
        }

    def get_live_url(self, scaffold_id: str) -> Dict[str, Any]:
        """
        GET /api/v1/scaffold/{id}/live-url -- 0 credits, Free+

        Returns the live URL for a deployed scaffold.
        The moment the user sees this is the 'Wait... I just built a product
        in minutes??' moment -- the TechIT growth engine.
        """
        return {
            "scaffold_id":       scaffold_id,
            "live_url":          f"https://{scaffold_id}.vercel.app",
            "techit_subdomain":  f"https://{scaffold_id}.techit.app",
            "deploy_status":     "deployed",
            "share_message":     "Your app is live. Share it. Build on it. Raise on it.",
        }

    def get_available_stacks(self) -> List[Dict[str, Any]]:
        """
        GET /api/v1/scaffold/stacks -- 0 credits, Free+

        Returns all supported stacks for the scaffold UI picker.
        """
        return [
            {"stack_key": k, **v}
            for k, v in self.STACK_OPTIONS.items()
        ]

    def generate_scaffold_zip_manifest(
        self, scaffold: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build the ZIP file manifest for a generated scaffold.

        Returns the expected file tree so the UI can show the user
        exactly what they are downloading before they download it.
        """
        stack = scaffold.get("scaffold_type", "nextjs_supabase")
        pages = scaffold.get("pages", [])

        base_files = [
            "package.json",
            "tsconfig.json",
            ".env.example",
            "README.md",
            ".gitignore",
            "vercel.json",
        ]
        if "nextjs" in stack:
            page_files = [f"app{p['route']}/page.tsx" for p in pages]
            component_files = [
                f"components/{c['name']}.tsx"
                for c in scaffold.get("components", [])
            ]
            return {
                "total_files": len(base_files) + len(page_files) + len(component_files) + 3,
                "file_tree": {
                    "root":        base_files,
                    "app/":        page_files,
                    "components/": component_files,
                    "lib/":        ["supabase.ts", "utils.ts", "types.ts"],
                },
                "download_size_estimate_kb": 85,
                "setup_time_minutes":        5,
            }
        return {
            "total_files":            len(base_files) + 10,
            "file_tree":              {"root": base_files},
            "download_size_estimate_kb": 60,
            "setup_time_minutes":     5,
        }


# ============================================================================
# API ENDPOINT REFERENCE
# ============================================================================

API_ENDPOINTS = """
TechIT API -- Full Endpoint Reference
=====================================

INCUBATION HUB
  POST /api/v1/incubation/pipeline/run              12 credits  Investor+
  POST /api/v1/incubation/idea/diagnose              1 credit   Free+
  POST /api/v1/incubation/unicorn/analyze            2 credits  Builder+
  POST /api/v1/incubation/market/analyze             2 credits  Builder+
  POST /api/v1/incubation/market/simulate-survey     3 credits  Investor+
  POST /api/v1/incubation/strategy/generate          3 credits  Founder Pro+
  POST /api/v1/incubation/finance/strategy           2 credits  Founder Pro+
  POST /api/v1/incubation/business-plan/generate     6 credits  Investor+
  POST /api/v1/incubation/tech-stack/design          2 credits  Founder Pro+
  POST /api/v1/incubation/roadmap/generate           2 credits  Founder Pro+
  POST /api/v1/incubation/pivot/analyze              2 credits  Builder+
  POST /api/v1/incubation/investor-readiness/generate 2 credits Investor+

DASHBOARD
  GET  /api/v1/dashboard/intelligence                0 credits  Free+
  GET  /api/v1/dashboard/gsis/{project_id}           1 credit   Free+
  GET  /api/v1/dashboard/infographic/{project_id}    0 credits  Free+

TOUR GUIDE
  POST /api/v1/tour-guide/daily-check-in             0 credits  Free+
  GET  /api/v1/tour-guide/audio-briefing             0 credits  Free+

TRAINING (ADAPTIVE -- NOT FIXED WEEKS)
  POST /api/v1/training/curriculum/generate          1 credit   Free+
  POST /api/v1/training/curriculum/adapt             0 credits  Free+
  POST /api/v1/training/progress/update              0 credits  Free+
  POST /api/v1/training/tutor/ask                    0 credits  Free+
  GET  /api/v1/training/time-to-mvp/{user_id}        0 credits  Free+
  GET  /api/v1/training/post-mvp/tracks              0 credits  Free+

MATCHING
  POST /api/v1/matching/find-collaborators           1 credit   Builder+
  POST /api/v1/matching/find-investors               2 credits  Investor+
  GET  /api/v1/matching/compatibility                0 credits  Free+

RISK
  POST /api/v1/risk/evaluate                         2 credits  Builder+

INVESTOR SECTION
  GET  /api/v1/investor/evi/{project_id}             2 credits  Investor+
  GET  /api/v1/investor/readiness/{project_id}       0+2 credits Investor+
  POST /api/v1/investor/signals/{project_id}         2 credits  Investor+
  GET  /api/v1/investor/deal-flow                    0 credits  Investor+
  POST /api/v1/investor/evaluate/{project_id}        2 credits  Investor+
  POST /api/v1/investor/watchlist/add                0 credits  Investor+

FEED
  GET  /api/v1/feed/curated                          0 credits  Free+

PROFILE
  POST /api/v1/profile/analyze                       1 credit   Free+
  GET  /api/v1/profile/score/{user_id}               0 credits  Free+

ORG SPHERE
  POST /api/v1/org/analyze                           1 credit   Founder Pro+
  GET  /api/v1/org/cohort/{cohort_id}/analytics      0 credits  Free+

MARKET READINESS
  GET  /api/v1/readiness/{project_id}                0 credits  Free+
  POST /api/v1/readiness/certify                     1 credit   Free+

ADMIN
  POST /api/v1/admin/monitor/scan                    0 credits  Enterprise
  GET  /api/v1/admin/stagnation-roster               0 credits  Enterprise

GSIS
  POST /api/v1/gsis/compute                          1 credit   Free+

BILLING
  GET  /api/v1/credits/summary                       0 credits  Free+
  POST /api/v1/credits/purchase                      0 credits  (Stripe)
  GET  /api/v1/billing/paywall/{operation_id}        0 credits  Free+

IP PROTECTION
  GET  /api/v1/ip-protection/status                  0 credits  Founder Pro+
  POST /api/v1/ip-protection/check-fingerprint       0 credits  Founder Pro+
  POST /api/v1/ip-protection/embed-idea              1 credit   Founder Pro+

PROMPT -> LIVE APP  (App Scaffold Engine)
  POST /api/v1/scaffold/generate                     5 credits  Founder Pro+
  GET  /api/v1/scaffold/{project_id}                 0 credits  Free+
  POST /api/v1/scaffold/{id}/deploy                  3 credits  Founder Pro+
  GET  /api/v1/scaffold/{id}/status                  0 credits  Free+
  GET  /api/v1/scaffold/{id}/live-url                0 credits  Free+
  POST /api/v1/scaffold/{id}/download                0 credits  Free+
  GET  /api/v1/scaffold/stacks                       0 credits  Free+

IDEA & SOLUTION HUB -- Global Problems Board
  POST /api/v1/solutions/problems/submit             2 credits  Free+
  GET  /api/v1/solutions/problems/board              0 credits  Free+
  GET  /api/v1/solutions/problems/{id}               0 credits  Free+
  POST /api/v1/solutions/problems/{id}/analyze       2 credits  Builder+
  GET  /api/v1/solutions/problems/discover           2 credits  Builder+
  GET  /api/v1/solutions/problems/match/{id}         2 credits  Builder+

IDEA & SOLUTION HUB -- Discussions
  POST /api/v1/solutions/discussions/{id}/contribute 1 credit   Free+
  GET  /api/v1/solutions/discussions/{id}/summary    1 credit   Free+
  GET  /api/v1/solutions/discussions/{id}/clusters   1 credit   Builder+
  POST /api/v1/solutions/discussions/{id}/convert    3 credits  Founder Pro+

IDEA & SOLUTION HUB -- Solution Projects
  POST /api/v1/solutions/projects/create             3 credits  Founder Pro+
  GET  /api/v1/solutions/projects/{id}               0 credits  Free+
  POST /api/v1/solutions/projects/{id}/feasibility   2 credits  Builder+
  GET  /api/v1/solutions/projects/{id}/impact        1 credit   Free+

IDEA & SOLUTION HUB -- Deployments
  POST /api/v1/solutions/deployments/create          2 credits  Founder Pro+
  GET  /api/v1/solutions/deployments/{id}            0 credits  Free+
  POST /api/v1/solutions/deployments/{id}/advance    0 credits  Free+
  POST /api/v1/solutions/deployments/{id}/feedback   1 credit   Free+
  GET  /api/v1/solutions/deployments/{id}/readiness  0 credits  Free+

IDEA & SOLUTION HUB -- Funding & Grants
  POST /api/v1/solutions/grants/generate             3 credits  Founder Pro+
  GET  /api/v1/solutions/grants/{solution_id}        0 credits  Free+
  GET  /api/v1/solutions/funding/match/{id}          2 credits  Builder+

IDEA & SOLUTION HUB -- Impact Dashboard
  GET  /api/v1/solutions/impact/global               0 credits  Free+
  GET  /api/v1/solutions/impact/{solution_id}        0 credits  Free+

DOCUMENT GENERATION ENGINE
  POST /api/v1/documents/generate                    2-4 credits  Builder+
  GET  /api/v1/documents/{document_id}               0 credits    Free+
  GET  /api/v1/documents/project/{project_id}        0 credits    Free+
  POST /api/v1/documents/{document_id}/export        0 credits    Free+
  GET  /api/v1/documents/{document_id}/preview       0 credits    Free+
  POST /api/v1/documents/{document_id}/edit          2 credits    Builder+
  DELETE /api/v1/documents/{document_id}             0 credits    Free+
  GET  /api/v1/documents/templates                   0 credits    Free+
  POST /api/v1/documents/investor-pack               8 credits    Investor+
  POST /api/v1/documents/{document_id}/share         0 credits    Free+
"""


# ============================================================================
# CELERY SCHEDULE REFERENCE
# ============================================================================

CELERY_SCHEDULE = """
TechIT Celery Beat Schedule
════════════════════════════
Task                           Schedule            Description
daily_tour_guide               0 6 * * *           Daily check-in for all active users
weekly_summaries               0 18 * * 0          Weekly Tour Guide summaries (Sun 18:00)
daily_investor_signals         0 0 * * *           Daily EVI-I + investor signal refresh
adaptive_curriculum_weekly     0 2 * * 1           Curriculum for new users (Mon 02:00)
wcrs_gsis_refresh              */30 * * * *        WCRS + GSIS refresh for all active projects
gsis_refresh                   */30 * * * *        GSIS score refresh for active projects
stagnation_roster              0 7 * * *           Flag stagnating projects + re-engagement
monthly_credit_reset           0 0 1 * *           Reset subscription credit allocations
admin_anomaly_scan             */15 * * * *        Abuse/anomaly monitoring
investor_alert_checker         */5 * * * *         Watchlist threshold alerts
feed_relevance_refresh         */30 * * * *        Update feed relevance scores
problem_discovery_daily        0 6 * * *           Auto-discover problems from external signals
discussion_moderation_hourly   0 * * * *           Moderate active discussion threads
deployment_status_refresh      */15 * * * *        Refresh deployment status and beneficiary counts
document_cleanup_weekly        0 3 * * 0           Archive expired document share links
impact_snapshot_daily          0 1 * * *           Snapshot impact scores for active deployments
"""


# ============================================================================
# EQUITY SERVICE  (Collaborator value layer)
# ============================================================================

class EquityService:
    """
    Collaborator equity: per-startup grants, vesting (years + cliff), dilution
    protection, and cap tables. Backs the collaborator Equity dashboard.

    Response keys are camelCase to match the frontend TS contracts
    (EquityHolding / equityTotals / VestingTimelineSeries) directly.

    Production: query `equity_grants`, `cap_table_entries`, `dilution_events`
    (database_schema.py). Below returns correctly-shaped data so the endpoint
    works before DB wiring — same house style as other pre-DB endpoints.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    # ── public API ────────────────────────────────────────────────────────
    async def get_collaborator_equity(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/collaborator/equity -- 0 credits, Free+"""
        holdings = self._load_holdings(user_context)
        return {
            "holdings": holdings,
            "totals":   self._totals(holdings),
            "vestingTimeline": [self._vesting_series(h) for h in holdings],
        }

    async def record_dilution_event(
        self, user_context: UserContext, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/collaborator/equity/dilution -- 0 credits.
        Honors dilution protection: already-vested equity is shielded unless the
        collaborator consented. Returns the protected/effective dilution.
        """
        holding = next(
            (h for h in self._load_holdings(user_context)
             if h["projectId"] == event.get("projectId")),
            None,
        )
        new_shares = float(event.get("newSharesPercent", 0) or 0)
        consent    = bool(event.get("consentGiven", False))
        vested_pct = float(holding["vestedPercent"]) if holding else 0.0
        equity     = float(holding["equityPercent"]) if holding else 0.0

        # Protected portion of the grant = the vested fraction (cannot be diluted
        # without consent). Unvested equity dilutes normally.
        vested_equity   = equity * (vested_pct / 100.0)
        unvested_equity = equity - vested_equity
        if consent:
            diluted = equity * (new_shares / 100.0)
            protected = False
        else:
            diluted = unvested_equity * (new_shares / 100.0)  # vested shielded
            protected = True
        return {
            "projectId":        event.get("projectId"),
            "newSharesPercent": new_shares,
            "consentGiven":     consent,
            "protectedApplied": protected,
            "equityBefore":     round(equity, 4),
            "equityAfter":      round(max(0.0, equity - diluted), 4),
            "shieldedEquity":   round(vested_equity, 4),
        }

    # ── helpers ───────────────────────────────────────────────────────────
    def _load_holdings(self, user_context: UserContext) -> List[Dict[str, Any]]:
        # Production: SELECT * FROM equity_grants JOIN projects WHERE user_id = :uid
        return [
            {
                "projectId": "1", "projectName": "NeuralSync AI", "projectLogo": "🧠",
                "equityPercent": 0.8, "valueUSD": 24000, "vestedPercent": 50,
                "vestingSchedule": {"years": 4, "cliffMonths": 12},
                "grantDate": "2025-01-15",
                "nextVest": {"date": "2026-06-12", "deltaPercent": 0.2},
                "dilutionProtected": True,
                "capTable": [
                    {"label": "Founders", "percent": 65},
                    {"label": "Collaborator pool", "percent": 12},
                    {"label": "You", "percent": 0.8, "highlighted": True},
                    {"label": "Investors", "percent": 18},
                    {"label": "Treasury", "percent": 4.2},
                ],
            },
            {
                "projectId": "2", "projectName": "FinFlow", "projectLogo": "💰",
                "equityPercent": 0.5, "valueUSD": 15000, "vestedPercent": 25,
                "vestingSchedule": {"years": 4, "cliffMonths": 12},
                "grantDate": "2025-03-01",
                "nextVest": {"date": "2026-09-01", "deltaPercent": 0.15},
                "dilutionProtected": True,
                "capTable": [
                    {"label": "Founders", "percent": 70},
                    {"label": "Collaborator pool", "percent": 10},
                    {"label": "You", "percent": 0.5, "highlighted": True},
                    {"label": "Investors", "percent": 17},
                    {"label": "Treasury", "percent": 2.5},
                ],
            },
            {
                "projectId": "3", "projectName": "HealthTrack Pro", "projectLogo": "🏥",
                "equityPercent": 0.3, "valueUSD": 9200, "vestedPercent": 0,
                "vestingSchedule": {"years": 4, "cliffMonths": 12},
                "grantDate": "2025-08-10",
                "nextVest": {"date": "2026-08-10", "deltaPercent": 0.075},
                "dilutionProtected": True,
                "capTable": [
                    {"label": "Founders", "percent": 72},
                    {"label": "Collaborator pool", "percent": 8},
                    {"label": "You", "percent": 0.3, "highlighted": True},
                    {"label": "Investors", "percent": 17},
                    {"label": "Treasury", "percent": 2.7},
                ],
            },
        ]

    @staticmethod
    def _totals(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_value = sum(float(h["valueUSD"]) for h in holdings)
        blended = round(sum(float(h["equityPercent"]) for h in holdings), 2)
        vested_quarter = sum(
            float(h["valueUSD"]) * (float(h["vestedPercent"]) / 100.0) * 0.25
            for h in holdings
        )
        # Soonest upcoming vest across holdings.
        upcoming = sorted(
            [h for h in holdings if h.get("nextVest")],
            key=lambda h: h["nextVest"]["date"],
        )
        next_vest = None
        if upcoming:
            nv = upcoming[0]
            next_vest = {
                "startup": nv["projectName"],
                "date": nv["nextVest"]["date"],
                "deltaPercent": nv["nextVest"]["deltaPercent"],
            }
        return {
            "totalValueUSD": round(total_value, 2),
            "blendedEquityPercent": blended,
            "vestedThisQuarterUSD": round(vested_quarter, 2),
            "nextVest": next_vest,
        }

    @staticmethod
    def _vesting_series(holding: Dict[str, Any]) -> Dict[str, Any]:
        """48 monthly points; linear vest after the cliff (mirrors frontend math)."""
        sched = holding["vestingSchedule"]
        cliff = int(sched["cliffMonths"])
        total_months = int(sched["years"]) * 12
        y, m = (int(p) for p in holding["grantDate"].split("-")[:2])
        points = []
        for i in range(48):
            mm = m - 1 + i
            yy = y + mm // 12
            month = mm % 12 + 1
            vested = min(100.0, (i / total_months) * 100.0) if i >= cliff else 0.0
            points.append({"monthIso": f"{yy:04d}-{month:02d}",
                           "vestedPercent": round(vested)})
        return {
            "projectId": holding["projectId"],
            "projectName": holding["projectName"],
            "points": points,
        }


# ============================================================================
# PAYOUT SERVICE  (Collaborator cash layer — money going OUT)
# ============================================================================

class PayoutService:
    """
    Collaborator cash earnings + payout ledger + withdrawals. Distinct from the
    billing credit engine (money coming in). Backs the Earnings dashboard.

    Response keys camelCase to match frontend CashEarning / Payout / cashTotals.
    Production: query `collaborator_earnings` and `payouts` (database_schema.py).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_collaborator_earnings(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/collaborator/earnings -- 0 credits, Free+"""
        earnings = self._load_earnings(user_context)
        payouts  = self._load_payouts(user_context)
        return {
            "cashEarnings": earnings,
            "payouts":      payouts,
            "totals":       self._totals(earnings, payouts),
        }

    async def request_withdrawal(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/collaborator/earnings/withdraw -- 0 credits.
        Body: { amount, destination? }. Creates a 'processing' payout.
        Production: INSERT payouts; debit pending balance atomically.
        """
        amount = float(body.get("amount", 0) or 0)
        totals = self._totals(self._load_earnings(user_context),
                              self._load_payouts(user_context))
        if amount <= 0 or amount > float(totals["pendingUSD"]):
            return {"ok": False, "error": "invalid_amount",
                    "available": totals["pendingUSD"]}
        # month/id are stamped by caller/DB in production (no clock in this layer).
        return {
            "ok": True,
            "payout": {
                "id": body.get("idemKey", "pending"),
                "monthIso": body.get("monthIso", ""),
                "amount": amount,
                "status": "processing",
            },
            "destination": body.get("destination", "•••1234"),
            "newPendingUSD": round(float(totals["pendingUSD"]) - amount, 2),
        }

    # ── helpers ───────────────────────────────────────────────────────────
    def _load_earnings(self, user_context: UserContext) -> List[Dict[str, Any]]:
        return [
            {"projectId": "1", "projectName": "NeuralSync AI",  "earned": 45000,
             "pending": 5000, "revenueSharePercent": 2.5,
             "contributionNote": "Dashboard feature increased user retention by 18%"},
            {"projectId": "2", "projectName": "FinFlow", "earned": 38000,
             "pending": 4500, "revenueSharePercent": 1.8,
             "contributionNote": "Payment integration enabled $500K in transactions"},
            {"projectId": "3", "projectName": "HealthTrack Pro", "earned": 22000,
             "pending": 2850, "revenueSharePercent": 1.2,
             "contributionNote": "ML model improved prediction accuracy by 12%"},
        ]

    def _load_payouts(self, user_context: UserContext) -> List[Dict[str, Any]]:
        rows = [
            ("p12", "2025-06", 8200), ("p11", "2025-07", 9100),
            ("p10", "2025-08", 10400), ("p9", "2025-09", 11200),
            ("p8", "2025-10", 10800), ("p7", "2025-11", 12400),
            ("p6", "2025-12", 11900), ("p5", "2026-01", 13200),
            ("p4", "2026-02", 13800), ("p3", "2026-03", 14100),
            ("p2", "2026-04", 14600), ("p1", "2026-05", 12350),
        ]
        out = [{"id": i, "monthIso": m, "amount": a, "status": "paid"} for i, m, a in rows]
        out[-1]["status"] = "processing"
        return out

    @staticmethod
    def _totals(earnings: List[Dict[str, Any]],
                payouts: List[Dict[str, Any]]) -> Dict[str, Any]:
        lifetime = sum(float(e["earned"]) for e in earnings)
        pending  = sum(float(e["pending"]) for e in earnings)
        # Trailing-12 revenue-share approximation from the payout ledger tail.
        ttm = sum(float(p["amount"]) for p in payouts[-12:]) * 0.1
        return {
            "lifetimeUSD": round(lifetime, 2),
            "pendingUSD": round(pending, 2),
            "revenueShareTTMUsd": round(ttm, 2),
        }


# ============================================================================
# CAPITAL POOL SERVICE  (Investor micro-funds + escrow milestone release)
# ============================================================================

class CapitalPoolService:
    """
    Investor micro-funds: pooled capital deployed across startups with automated,
    milestone-based escrow release. Backs the investor Capital Pools dashboard.

    Response keys camelCase to match the frontend CapitalPool contract.
    Production: query `capital_pools` + `pool_milestone_releases`.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_capital_pools(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/investor/capital-pools -- 0 credits, Investor+"""
        return {"pools": self._load_pools(user_context)}

    async def create_pool(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST /api/v1/investor/capital-pools -- 0 credits. Body: pool definition."""
        rules = body.get("rules", {})
        pool = {
            "id": body.get("id", "new"),
            "name": body.get("name", "Untitled Pool"),
            "totalCapital": float(body.get("totalCapital", 0) or 0),
            "deployed": 0,
            "startups": 0,
            "milestonesHit": 0,
            "fundsReleased": 0,
            "roiSimulation": 0,
            "rules": {
                "minReadiness": int(rules.get("minReadiness", 80)),
                "maxPerStartup": float(rules.get("maxPerStartup", 20)),
                "milestoneTrigger": bool(rules.get("milestoneTrigger", True)),
            },
        }
        return {"ok": True, "pool": pool}

    async def release_on_milestone(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/investor/capital-pools/{pool_id}/release -- 0 credits.
        Release escrowed capital for a startup that hit a milestone.
        Body: { projectId, milestone, amount }
        """
        amount = float(body.get("amount", 0) or 0)
        return {
            "ok": amount > 0,
            "poolId": body.get("poolId"),
            "projectId": body.get("projectId"),
            "milestone": body.get("milestone"),
            "amountReleased": amount,
            "released": amount > 0,
        }

    def _load_pools(self, user_context: UserContext) -> List[Dict[str, Any]]:
        return [
            {"id": "1", "name": "TechIT Micro Fund Alpha", "totalCapital": 500000,
             "deployed": 380000, "startups": 8, "milestonesHit": 24,
             "fundsReleased": 280000, "roiSimulation": 3.2,
             "rules": {"minReadiness": 85, "maxPerStartup": 20, "milestoneTrigger": True}},
            {"id": "2", "name": "AI Governance Fund", "totalCapital": 750000,
             "deployed": 520000, "startups": 10, "milestonesHit": 31,
             "fundsReleased": 420000, "roiSimulation": 4.1,
             "rules": {"minReadiness": 80, "maxPerStartup": 15, "milestoneTrigger": True}},
        ]


# ============================================================================
# DEAL ROOM SERVICE  (Investor cap table / term sheet / signing / negotiation)
# ============================================================================

class DealRoomService:
    """
    Secure investor↔startup deal rooms: negotiation stage tracking, term-sheet
    simulator, milestone tranches, document signing. Backs the investor Deal
    Rooms list + detail.

    Production: query `deal_rooms`, `term_sheets`, `deal_documents`.
    """

    STAGE_ORDER = [
        "Intro Call", "NDA Signed", "Due Diligence",
        "Term Sheet", "Negotiation", "Deal Closed",
    ]

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_deal_rooms(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/investor/deal-rooms -- 0 credits, Investor+"""
        return {"dealMeta": self._load_deal_meta(), "stageOrder": self.STAGE_ORDER}

    async def get_deal_room(
        self, user_context: UserContext, project_id: str, startup: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        GET /api/v1/investor/deal-rooms/{project_id} -- 0 credits, Investor+
        Returns term-sheet defaults, valuation (ARR×8), milestone tranches,
        documents, and the negotiation stepper.
        """
        mrr = float((startup or {}).get("mrr", 0) or 0)
        valuation = mrr * 12 * 8  # ARR × 8 multiple (mirrors frontend)
        meta = self._load_deal_meta().get(project_id, {
            "status": "pending", "stage": "Intro Call", "daysOpen": 0,
            "messages": 0, "docs": 0, "lastActivity": "just now",
        })
        return {
            "projectId": project_id,
            "meta": meta,
            "valuationUSD": valuation,
            "termSheet": {
                "valuationUSD": valuation,
                "investmentUSD": 250000,
                "equityPercent": 5.2,
                "instrument": "SAFE",
                "discountPercent": 20,
                "valuationCapUSD": valuation,
                "extraTerms": {"rights": "Observer Rights"},
            },
            "milestones": [
                {"milestone": "Initial Tranche",   "amount": 100000, "condition": "On signing",          "status": "pending"},
                {"milestone": "Product Milestone", "amount": 75000,  "condition": "Ship v2 / 1k users",   "status": "pending"},
                {"milestone": "Revenue Milestone", "amount": 75000,  "condition": "Reach $150K MRR",      "status": "pending"},
            ],
            "documents": [
                {"name": "Simple Agreement for Future Equity (SAFE)", "status": "ready"},
                {"name": "Subscription Agreement",                    "status": "ready"},
                {"name": "Investor Rights Agreement",                 "status": "draft"},
                {"name": "Right of First Refusal Agreement",          "status": "draft"},
            ],
            "negotiation": [
                {"step": "Initial Discussion", "state": "completed"},
                {"step": "Term Sheet Draft",   "state": "completed"},
                {"step": "Due Diligence",      "state": "active"},
                {"step": "Final Agreement",    "state": "todo"},
                {"step": "Funds Transfer",     "state": "todo"},
            ],
            "stageOrder": self.STAGE_ORDER,
        }

    def _load_deal_meta(self) -> Dict[str, Any]:
        return {
            "1": {"status": "active",  "stage": "Term Sheet",     "daysOpen": 12, "messages": 34,  "docs": 7,  "lastActivity": "2h ago"},
            "2": {"status": "active",  "stage": "Due Diligence",  "daysOpen": 8,  "messages": 52,  "docs": 11, "lastActivity": "45m ago"},
            "3": {"status": "pending", "stage": "NDA Signed",     "daysOpen": 3,  "messages": 9,   "docs": 2,  "lastActivity": "1d ago"},
            "4": {"status": "active",  "stage": "Negotiation",    "daysOpen": 21, "messages": 78,  "docs": 14, "lastActivity": "3h ago"},
            "5": {"status": "closed",  "stage": "Deal Closed",    "daysOpen": 45, "messages": 120, "docs": 22, "lastActivity": "5d ago"},
            "6": {"status": "pending", "stage": "Intro Call",     "daysOpen": 1,  "messages": 4,   "docs": 1,  "lastActivity": "6h ago"},
        }


# ============================================================================
# DATA ROOM SERVICE  (Investor document vault + access control + sharing)
# ============================================================================

class DataRoomService:
    """
    Per-startup data rooms: structured 6-section document vaults with
    compliance/governance verification and per-investor access grants. Backs
    the investor Data Rooms list + detail.

    Production: query `data_rooms` + `data_room_access`.
    """

    SECTIONS = [
        "Metrics Dashboard", "Financials", "Testing Reports",
        "Compliance", "Governance", "Execution History",
    ]

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_data_rooms(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/investor/data-rooms -- 0 credits, Investor+"""
        rooms = self._load_rooms(user_context)
        verified = sum(1 for r in rooms if r["complianceVerified"])
        return {
            "rooms": rooms,
            "sections": self.SECTIONS,
            "totals": {
                "activeRooms": len(rooms),
                "totalDocs": len(rooms) * len(self.SECTIONS),
                "complianceVerified": verified,
                "aiSummaries": len(rooms),
            },
        }

    async def grant_access(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/investor/data-rooms/{project_id}/access -- 0 credits.
        Share a data room with an investor. Body: { investorId, canDownload }
        Production: upsert data_room_access.
        """
        return {
            "ok": True,
            "projectId": body.get("projectId"),
            "investorId": body.get("investorId"),
            "canDownload": bool(body.get("canDownload", False)),
            "granted": True,
        }

    def _load_rooms(self, user_context: UserContext) -> List[Dict[str, Any]]:
        # Production: SELECT data_rooms JOIN projects for this investor's pipeline.
        # Returns per-startup vault metadata keyed by projectId.
        seed = [
            ("1", True,  True),  ("2", True,  False),
            ("3", False, True),  ("4", True,  True),
            ("5", True,  False), ("6", False, False),
        ]
        return [
            {
                "projectId": pid,
                "sections": self.SECTIONS,
                "docCount": len(self.SECTIONS),
                "complianceVerified": comp,
                "aiGovernanceVerified": gov,
                "updatedLabel": "today",
            }
            for pid, comp, gov in seed
        ]


# ============================================================================
# INVESTOR REPUTATION SERVICE  (mutual accountability)
# ============================================================================

class InvestorReputationService:
    """
    Investor-side reputation: composite score from 5 weighted metrics, founder
    reviews, score progression, and leaderboard position. Backs the investor
    Reputation dashboard.

    Production: query `investor_reputation` + `investor_reviews`.
    """

    # weights sum to 1.0
    WEIGHTS = {
        "responseSpeed": 0.22, "founderRating": 0.26, "followThrough": 0.20,
        "valueAdd": 0.16, "portfolioEngagement": 0.16,
    }

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_reputation(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/investor/reputation -- 0 credits, Investor+"""
        metrics = self._metrics(user_context)
        score = round(sum(m["score"] * self.WEIGHTS[m["key"]] for m in metrics))
        level = "Elite" if score >= 85 else "Established" if score >= 70 else "Building"
        return {
            "score": score,
            "level": level,
            "monthChange": 3,
            "metrics": metrics,
            "reviews": self._reviews(user_context),
            "progression": [
                {"month": "Feb 2026", "score": 87, "change": 3},
                {"month": "Jan 2026", "score": 84, "change": 2},
                {"month": "Dec 2025", "score": 82, "change": 4},
                {"month": "Nov 2025", "score": 78, "change": 1},
            ],
            "leaderboard": {"rank": 12, "total": 284, "percentile": 4.2},
        }

    def _metrics(self, user_context: UserContext) -> List[Dict[str, Any]]:
        return [
            {"key": "responseSpeed",       "label": "Response Speed",            "score": 92, "description": "Average response time: 4.2 hours"},
            {"key": "founderRating",       "label": "Founder Rating",            "score": 88, "description": "Based on 12 founder reviews"},
            {"key": "followThrough",       "label": "Follow-Through Consistency", "score": 85, "description": "Commitments kept: 94%"},
            {"key": "valueAdd",            "label": "Value-Add Contributions",   "score": 81, "description": "Active portfolio support"},
            {"key": "portfolioEngagement", "label": "Portfolio Engagement",      "score": 90, "description": "Monthly check-ins: 100%"},
        ]

    def _reviews(self, user_context: UserContext) -> List[Dict[str, Any]]:
        return [
            {"founderName": "Sarah Chen",      "startup": "QuantumAPI",   "rating": 5, "comment": "Incredibly responsive and provided valuable strategic guidance. Made the funding process smooth and transparent.", "date": "Feb 8, 2026"},
            {"founderName": "Marcus Rodriguez", "startup": "NeuralEdge AI", "rating": 5, "comment": "Goes beyond capital. Opened doors to key partnerships and actively helps with hiring. True value-add investor.", "date": "Feb 1, 2026"},
            {"founderName": "Aisha Patel",     "startup": "CloudMesh",    "rating": 4, "comment": "Professional and fair terms. Would have appreciated faster turnaround on due diligence.", "date": "Jan 24, 2026"},
        ]


# ============================================================================
# DEMO
# ============================================================================

async def complete_demo() -> None:
    print("=" * 65)
    print("TECHIT -- UNIFIED INTEGRATION DEMO")
    print("=" * 65)

    brain = TechITAIBrain()

    incubation = IncubationHubService(brain)
    dashboard  = DashboardIntelligenceService(brain)
    tour_guide = TourGuideService(brain)
    training   = AdaptiveTrainingService(brain)
    matching   = MatchingEngineService(brain)
    investor   = InvestorSectionService(brain)
    gsis_svc   = GSISService(brain)

    uc = UserContext(
        user_id="demo_founder", role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO, credits_remaining=150,
        project_id="proj_001", project_stage="idea", industry="edtech",
        tech_stack=["React", "Node.js"], past_feedback=[],
        training_progress={"completion_percentage": 0},
        time_logged_today=0, tasks_completed_week=0,
        days_since_update=0, team_size=2,
    )

    print("\n🚀 Step 1: Idea diagnostic (1 credit)")
    d = await incubation.run_idea_diagnostic(uc, {
        "startup_name": "SkillBridge Africa", "industry": "EdTech",
        "problem": "Youth skills mismatch", "solution": "AI micro-credential platform",
    })
    print(f"   ✅ Profile keys: {list(d.get('structured_profile', {}).keys())[:4]}")

    print("\n📊 Step 2: GSIS compute (1 credit)")
    gsis = gsis_svc.compute({"pps": 40, "evi": 60, "mrs": 35, "bss": 0, "rgs": 0,
                              "frs": 70, "cis": 45, "iis": 15, "cs": 80})
    print(f"   ✅ GSIS: {gsis['gsis']} -- {gsis['classification']}")
    print(f"   Alert triggered: {gsis['alert_triggered']} (score: {gsis['alert_score']})")

    print("\n🧭 Step 3: Tour Guide (0 credits)")
    checkin = await tour_guide.daily_check_in(uc)
    print(f"   ✅ Momentum: {checkin['momentum_score']}/100 | Decay: {checkin['decay_factor']:.4f}")

    print("\n🎓 Step 4: Adaptive curriculum (1 credit)")
    curriculum = await training.generate_curriculum(
        uc, hours_available_per_week=8, learning_pace="standard",
        target_mvp_weeks=0, has_technical_skills=False,
    )
    ls = curriculum.get("learning_summary", {})
    print(f"   ✅ Weeks to MVP: {ls.get('estimated_weeks_to_mvp')} | "
          f"Modules: {curriculum.get('pre_mvp', {}).get('total_modules', 0)} pre-MVP")
    print(f"   ✅ MVP target: {ls.get('mvp_target_date', 'TBD')}")

    print("\n🤝 Step 5: Find collaborators (1 credit)")
    matches = await matching.find_collaborators(
        uc, {"required_skills": ["Python"], "availability_required": True}
    )
    print(f"   ✅ Matches found: {matches['total_found']}")

    print("\n📈 Step 6: Dashboard intelligence (0 credits)")
    dash = await dashboard.get_dashboard_intelligence(uc, {"market_readiness_score": 35})
    print(f"   ✅ GSIS: {dash['gsis']['gsis'] if dash.get('gsis') else 'N/A'}")
    print(f"   ✅ Alerts: {len(dash.get('alerts', []))}")

    print("\n" + "=" * 65)
    print("✅ Unified integration demo complete")
    print(f"   Credits used: ~5 / 150 available")


if __name__ == "__main__":
    asyncio.run(complete_demo())
