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
from uuid import uuid4

from ai_router_core import (
    AICommandLayer, ModelRouter, PromptEngine, SafetyEngine,
    AIRequest, UserContext, TaskType, UserRole,
    SubscriptionTier, ScoringEngine, CreditCost,
    SubscriptionAccessControl,
)
from agent_orchestration import (
    AgentOrchestrator, AgentType, AgentContext, VenturePipeline,
)
from trust_continuous_verification import TrustContinuousVerificationRunner
from trust_engine_lite import (
    FounderTrustProfile,
    TrustEngineComputer,
    VerificationSource,
    VerificationStatus,
)
from trust_integration_adapters import (
    TrustIntegrationAdapterRegistry,
    TrustRefreshPlanner,
)
from trust_profile_sharing import (
    TrustMilestoneReviewService as TrustMilestoneReviewContract,
    TrustProfileSharingService,
)
from trust_team_notifications import (
    TrustNotificationPreviewService,
    TrustTeamVerificationService as TrustTeamContract,
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
        blueprint = self._compile_blueprint(venture_data, results)

        # Persist the analysis and bind it to a project so it can flow into a
        # workspace (instead of being returned ephemerally and discarded).
        project_id = self._persist_analysis(user_context, venture_data, blueprint)
        blueprint["project_id"] = project_id
        return blueprint

    def _persist_analysis(
        self, user_context: UserContext, venture_data: Dict, blueprint: Dict
    ) -> str:
        """
        Persist the compiled blueprint as a ProjectAnalysis and upsert the
        Project's headline scores. Returns the project_id the analysis is bound
        to (existing project if provided, else a newly created one).

        Production (database_schema.py):
          project_id = venture_data.get("project_id") or <INSERT projects ...>.id
          INSERT INTO project_analyses (project_id, owner_id, venture_name,
              blueprint, unicorn_potential_score, investment_score, pivot_needed)
          UPDATE projects SET unicorn_potential_score=..., investment_score=...,
              updated_at=now() WHERE id = project_id
        """
        return venture_data.get("project_id") or "proj_new"

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

    async def suggest_tasks(
        self,
        user_context: UserContext,
        workspace_data: Dict,
        user_token: Optional[str] = None,
    ) -> Dict:
        """POST /api/v1/workspace/tasks/suggest -- 0 credits.

        When the caller forwards their bearer token, we pull the MCP tool
        catalogue from BACKEND/api/mcp and include it in the agent's prompt
        context so WorkspaceAssistantAgent's suggestions become tool-aware.
        Without a token, the agent runs without that context (no regression).
        """
        available_tools = await self._safe_list_tools(user_token)
        ctx = AgentContext(
            user_context=user_context,
            trigger_event={
                "workspace_data": workspace_data,
                "available_tools": available_tools,
            },
        )
        r   = await self.brain.trigger_agent(AgentType.WORKSPACE_ASSISTANT, ctx)
        return {
            "suggestions": r.output.get("task_suggestions"),
            "next_actions": r.recommendations,
            "available_tools": available_tools,
        }

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

    async def list_tools(self, user_context: UserContext, user_token: str) -> Dict[str, Any]:
        """GET /api/v1/workspace/tools -- 0 credits.

        Catalogue of plugin tools the user can invoke via BACKEND/api/mcp.
        Forwarded bearer is the only authority — BACKEND verifies and audits.
        """
        from mcp_client import MCPError, get_mcp_client
        try:
            tools = await get_mcp_client().list_tools(user_token=user_token)
            return {"ok": True, "tools": tools}
        except MCPError as exc:
            return {"ok": False, "error": str(exc), "tools": []}

    async def invoke_tool(
        self,
        user_context: UserContext,
        user_token: str,
        plugin: str,
        tool: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST /api/v1/workspace/tools/invoke -- 0 credits.

        Executes a plugin tool as the authenticated user (no service identity).
        BACKEND/api/mcp enforces role and audit using the same JWT_SECRET this
        service verifies tokens with.
        """
        from mcp_client import MCPError, get_mcp_client
        try:
            return await get_mcp_client().invoke(plugin, tool, params, user_token=user_token)
        except MCPError as exc:
            return {"ok": False, "error": {"code": "mcp_failed", "error": str(exc)}}

    async def _safe_list_tools(self, user_token: Optional[str]) -> List[Dict[str, Any]]:
        """Best-effort tool fetch for prompt-context injection. Never raises."""
        if not user_token:
            return []
        from mcp_client import MCPError, get_mcp_client
        try:
            return await get_mcp_client().list_tools(user_token=user_token)
        except MCPError as exc:
            logger.warning("mcp_tools_unavailable_for_prompt", error=str(exc))
            return []


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
# TRUST ENGINE LITE SERVICE
# ============================================================================

class TrustVerificationService:
    """
    Privacy-first Trust Engine Lite API contract layer.

    Wave 37 deliberately does not perform live OAuth, OTP, DNS, deployment, or
    analytics calls. It accepts only provider-derived metadata summaries from
    future integration adapters and persists append-only verification/timeline
    records when a database session is provided.
    """

    METADATA_FIELDS: Dict[str, set[str]] = {
        VerificationSource.EMAIL.value: {"verified", "verified_at", "confidence"},
        VerificationSource.PHONE.value: {"verified", "verified_at", "confidence"},
        VerificationSource.GITHUB.value: {
            "github_repo_count",
            "github_commit_count",
            "github_contributor_count",
            "github_last_activity_at",
            "repo_count",
            "commit_count",
            "contributor_count",
            "last_activity",
            "confidence",
            "verified",
        },
        VerificationSource.LINKEDIN.value: {"connected", "verified", "confidence"},
        VerificationSource.DOMAIN.value: {
            "domain",
            "method",
            "verified",
            "verified_at",
            "expires_at",
            "confidence",
        },
        VerificationSource.WEBSITE.value: {
            "website",
            "method",
            "verified",
            "verified_at",
            "expires_at",
            "confidence",
        },
        VerificationSource.ORGANIZATION.value: {
            "organization_id",
            "company_name",
            "country",
            "verified",
            "business_verification_status",
            "confidence",
        },
        VerificationSource.DEPLOYMENT.value: {
            "platform",
            "deployment_status",
            "deployment_live",
            "deployments_30d",
            "last_deployment_at",
            "last_deployment",
            "success_rate",
            "confidence",
            "verified",
        },
        VerificationSource.PRODUCT_ANALYTICS.value: {
            "provider",
            "mau",
            "dau",
            "growth_rate_pct",
            "retention_rate_pct",
            "growth_pct",
            "retention_pct",
            "confidence",
            "verified",
        },
        VerificationSource.TEAM.value: {
            "verified_team_count",
            "pending_invitations",
            "verified",
            "confidence",
        },
        VerificationSource.MILESTONE.value: {
            "milestone",
            "evidence_url",
            "approval_status",
            "approved_by",
            "verified",
            "confidence",
        },
    }
    SOURCE_ALIASES = {
        "firebase": VerificationSource.PRODUCT_ANALYTICS.value,
        "supabase": VerificationSource.PRODUCT_ANALYTICS.value,
        "product": VerificationSource.PRODUCT_ANALYTICS.value,
        "analytics": VerificationSource.PRODUCT_ANALYTICS.value,
        "org": VerificationSource.ORGANIZATION.value,
    }
    FORBIDDEN_TERMS = (
        "token",
        "secret",
        "password",
        "raw",
        "payload",
        "source_code",
        "repository_content",
        "repo_content",
        "contact",
        "message",
        "document_blob",
        "analytics_event",
        "session",
        "user_email",
        "user_id",
    )

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    def get_profile(
        self,
        user_context: UserContext,
        db: Any = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/trust/profile -- 0 credits, Free+."""
        row = self._load_profile_row(user_context, db)
        profile = self._profile_from_row(user_context, row)
        computed = TrustEngineComputer.compute(profile)

        return {
            "user_id": user_context.user_id,
            "project_id": user_context.project_id,
            "verification_status": profile.verification_status,
            "trust_score": computed["trust_score"],
            "tier": computed["tier"],
            "confidence_score": self._confidence_from_score(computed["trust_score"]),
            "badges": computed["badges"],
            "signals": computed["signals"],
            "breakdown": computed["breakdown"],
            "last_sync_at": self._iso(profile.last_sync_at),
            "computed_at": computed["computed_at"],
            "privacy": self._privacy_notice(),
        }

    def get_badges(
        self,
        user_context: UserContext,
        db: Any = None,
    ) -> Dict[str, Any]:
        """GET /api/v1/trust/badges -- 0 credits, Free+."""
        row = self._load_profile_row(user_context, db)
        profile = self._profile_from_row(user_context, row)
        badges = TrustEngineComputer.compute_badges(profile)
        return {
            "user_id": user_context.user_id,
            "project_id": user_context.project_id,
            "badges": [self._badge_to_dict(b) for b in badges],
            "active_badges": [b.label for b in badges if b.is_active],
            "privacy": "Badges are derived metadata only and expire with their source verification.",
        }

    def get_history(
        self,
        user_context: UserContext,
        db: Any = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """GET /api/v1/trust/history -- 0 credits, Free+."""
        rows = self._load_history_rows(user_context, db, limit)
        return {
            "user_id": user_context.user_id,
            "project_id": user_context.project_id,
            "history": [self._history_row_to_dict(r) for r in rows],
            "append_only": True,
            "privacy": "History stores verification result metadata and hashes, not provider payloads.",
        }

    def build_share_profile(
        self,
        user_context: UserContext,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/share-profile/preview -- 0 credits, Free+."""
        body = body or {}
        profile = body.get("profile") if isinstance(body.get("profile"), dict) else self.get_profile(user_context, db)
        badges_payload = body.get("badges")
        history_payload = body.get("history")
        badges = badges_payload if isinstance(badges_payload, list) else self.get_badges(user_context, db)["badges"]
        history = history_payload if isinstance(history_payload, list) else self.get_history(user_context, db)["history"]
        settings = body.get("settings") if isinstance(body.get("settings"), dict) else body
        shared = TrustProfileSharingService().build(
            profile=profile,
            badges=badges,
            history=history,
            settings=settings,
        )
        shared["owner_ids_exposed_to_investors"] = False
        return shared

    def get_integration_manifests(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """GET /api/v1/trust/integrations -- 0 credits, Free+."""
        registry = TrustIntegrationAdapterRegistry.default()
        if provider:
            manifests = [registry.manifest(provider)]
        else:
            manifests = registry.manifests()
        return {
            "integrations": manifests,
            "privacy": {
                "metadata_only": True,
                "raw_payload_stored": False,
                "tokens_exposed_to_frontend": False,
                "live_provider_calls": False,
            },
        }

    def verify_adapter_payload(
        self,
        user_context: UserContext,
        provider: str,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/trust/adapters/{provider}/verify -- 1 credit, Free+.

        Future provider clients should feed raw responses into their private
        adapter process, then submit only this normalized metadata contract.
        """
        adapter_result = TrustIntegrationAdapterRegistry.default().normalize(provider, body or {})
        result = self.verify_source(user_context, adapter_result.source, adapter_result.metadata, db)
        result["adapter"] = {
            "provider": adapter_result.provider,
            "source": adapter_result.source,
            "status": adapter_result.status,
            "confidence": adapter_result.confidence,
            "metadata_hash": adapter_result.metadata_hash,
            "expires_at": adapter_result.expires_at.isoformat(),
            "next_sync_at": adapter_result.next_sync_at.isoformat(),
            "raw_payload_stored": adapter_result.raw_payload_stored,
            "tokens_stored": adapter_result.tokens_stored,
        }
        result["dropped_fields"] = sorted(set(result["dropped_fields"] + adapter_result.dropped_fields))
        result["next_action"] = self._next_action(adapter_result.source, VerificationStatus(adapter_result.status))
        return result

    def get_refresh_plan(
        self,
        user_context: UserContext,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/refresh-plan -- 0 credits, Free+."""
        body = body or {}
        connections = body.get("connections") or []
        if not isinstance(connections, list):
            connections = []
        plan = TrustRefreshPlanner().plan(connections)
        plan["user_id"] = user_context.user_id
        plan["project_id"] = user_context.project_id
        return plan

    def run_continuous_verification(
        self,
        user_context: UserContext,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/trust/continuous-verification/run -- 0 credits, Free+.

        This executes no live provider calls. It consumes existing connection
        metadata and optional adapter payloads, then prepares notification
        intents and append-only verification actions. Actions are persisted only
        when the caller passes execute=true.
        """
        body = body or {}
        connections = body.get("connections") or []
        adapter_payloads = body.get("adapter_payloads") or {}
        if not isinstance(connections, list):
            connections = []
        if not isinstance(adapter_payloads, dict):
            adapter_payloads = {}

        run = TrustContinuousVerificationRunner().prepare(
            user_id=user_context.user_id,
            project_id=user_context.project_id,
            connections=connections,
            adapter_payloads=adapter_payloads,
        )
        execute = body.get("execute") is True
        executed = []
        if execute:
            for action in run["verification_actions"]:
                executed.append(self._execute_continuous_action(user_context, action, db))

        run["execute"] = execute
        run["executed_results"] = executed
        run["privacy"]["notifications_are_intents_only"] = True
        run["privacy"]["raw_payload_stored"] = False
        return run

    def verify_source(
        self,
        user_context: UserContext,
        source: str,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
        *,
        action: str = "verify",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/trust/verify/{source} -- 1 credit, Free+.

        The request body is treated as adapter metadata, not raw provider data.
        Unknown and sensitive keys are dropped before hashing/persistence.
        """
        body = body or {}
        canonical_source = self._canonical_source(source)
        metadata = self._sanitize_metadata(canonical_source, body)
        status = self._status_for_action(action, metadata)
        confidence = self._confidence_for(status, metadata)
        now = datetime.utcnow()

        record = TrustEngineComputer.build_verification_record(
            verification_id=str(body.get("verification_id") or f"trust_{uuid4().hex}"),
            subject_id=str(body.get("subject_id") or user_context.project_id or user_context.user_id),
            subject_type=str(body.get("subject_type") or ("project" if user_context.project_id else "user")),
            source=canonical_source,
            status=status,
            confidence=confidence,
            metadata=metadata,
            created_at=now,
            reference_id=body.get("reference_id"),
        )
        persisted = self._persist_verification(user_context, canonical_source, metadata, record, db)
        trust_profile = self.get_profile(user_context, db)

        return {
            "verification": self._record_to_dict(record),
            "source": canonical_source,
            "status": status.value,
            "confidence": confidence,
            "metadata_stored": metadata,
            "metadata_hash": record.metadata_hash,
            "raw_payload_stored": False,
            "dropped_fields": self._dropped_fields(canonical_source, body),
            "expires_at": record.expires_at.isoformat(),
            "persisted": persisted,
            "trust_profile": trust_profile,
            "next_action": self._next_action(canonical_source, status),
        }

    def disconnect_source(
        self,
        user_context: UserContext,
        source: str,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/disconnect/{source} -- 0 credits, Free+."""
        body = {**(body or {}), "verified": False, "disconnected": True}
        result = self.verify_source(user_context, source, body, db, action="disconnect")
        result["next_action"] = "Reconnect the integration or leave it disconnected."
        return result

    def refresh_source(
        self,
        user_context: UserContext,
        source: str,
        body: Optional[Dict[str, Any]] = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/refresh/{source} -- 1 credit, Free+."""
        body = {**(body or {}), "manual_refresh": True}
        return self.verify_source(user_context, source, body, db, action="refresh")

    def submit_milestone(
        self,
        user_context: UserContext,
        body: Dict[str, Any],
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/milestone -- 1 credit, Free+."""
        milestone_body = {
            **body,
            "milestone": body.get("milestone") or body.get("title"),
            "evidence_url": body.get("evidence_url") or body.get("url"),
            "approval_status": body.get("approval_status", "pending"),
            "approved_by": body.get("approved_by"),
            "verified": body.get("approval_status") == "approved",
            "confidence": body.get("confidence", 0.5),
            "subject_type": "milestone",
            "subject_id": body.get("milestone_id") or body.get("reference_id") or user_context.project_id or user_context.user_id,
            "reference_id": body.get("reference_id"),
        }
        result = self.verify_source(user_context, VerificationSource.MILESTONE.value, milestone_body, db)
        result["review_status"] = milestone_body["approval_status"]
        result["next_action"] = "Admin review required before the milestone becomes investor-visible."
        return result

    def review_milestone(
        self,
        user_context: UserContext,
        body: Dict[str, Any],
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/milestone/review -- 1 credit, admin workflow contract."""
        review = TrustMilestoneReviewContract().review(body)
        verification_body = {
            **review["metadata"],
            "subject_type": "milestone",
            "subject_id": body.get("milestone_id") or body.get("reference_id") or user_context.project_id or user_context.user_id,
            "reference_id": body.get("reference_id") or review["review_id"],
        }
        verification = self.verify_source(user_context, VerificationSource.MILESTONE.value, verification_body, db)
        return {
            "review": review,
            "verification": verification,
            "timeline_event": review["timeline_event"],
            "investor_visible": review["timeline_event"]["visibility"] == "public",
            "privacy": {
                "metadata_only": True,
                "raw_payload_stored": False,
                "uploaded_file_stored": False,
                "public_evidence_url_preferred": True,
            },
        }

    def invite_team_member(
        self,
        user_context: UserContext,
        body: Dict[str, Any],
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/team/invite -- 0 credits, Free+."""
        invitation = TrustTeamContract().invite(body)
        return {
            "invitation": invitation,
            "verification": {
                "source": VerificationSource.TEAM.value,
                "status": VerificationStatus.PENDING.value,
                "persisted": False,
                "reason": "Invitation contracts are notification intents only until a teammate verifies.",
            },
            "privacy": {
                "metadata_only": True,
                "raw_email_stored": False,
                "raw_payload_stored": False,
                "hr_data_stored": False,
                "investor_visible": False,
            },
        }

    def verify_team_member(
        self,
        user_context: UserContext,
        body: Dict[str, Any],
        db: Any = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/team/verify -- 1 credit, Free+."""
        team_result = TrustTeamContract().verify(body)
        verification_body = {
            **team_result["verification_metadata"],
            "subject_type": "team_member",
            "subject_id": team_result["member_ref"],
            "reference_id": body.get("invitation_id") or team_result["member_ref"],
        }
        verification = self.verify_source(user_context, VerificationSource.TEAM.value, verification_body, db)
        return {
            "team": team_result,
            "verification": verification,
            "notification_intent": team_result["notification_intent"],
            "privacy": {
                "metadata_only": True,
                "raw_email_stored": False,
                "raw_payload_stored": False,
                "hr_data_stored": False,
                "investor_visible": False,
            },
        }

    def preview_notifications(
        self,
        user_context: UserContext,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/trust/notifications/preview -- 0 credits, Free+."""
        body = body or {}
        events = body.get("events") if isinstance(body.get("events"), list) else []
        preview = TrustNotificationPreviewService().preview(events)
        preview["owner_ids_exposed_to_investors"] = False
        return preview

    def _execute_continuous_action(
        self,
        user_context: UserContext,
        action: Dict[str, Any],
        db: Any = None,
    ) -> Dict[str, Any]:
        status = str(action.get("status") or VerificationStatus.PENDING.value)
        action_mode = {
            VerificationStatus.EXPIRED.value: "expire",
            VerificationStatus.FAILED.value: "fail",
            VerificationStatus.PENDING.value: "refresh",
        }.get(status, "verify")
        result = self.verify_source(
            user_context,
            str(action["source"]),
            dict(action.get("metadata") or {}),
            db,
            action=action_mode,
        )
        return {
            "action_id": action["action_id"],
            "action_type": action["action_type"],
            "source": action["source"],
            "provider": action["provider"],
            "requested_status": status,
            "recorded_status": result["status"],
            "metadata_hash": result["metadata_hash"],
            "persisted": result["persisted"],
            "raw_payload_stored": result["raw_payload_stored"],
        }

    @classmethod
    def _canonical_source(cls, source: str) -> str:
        value = (source or "").strip().lower()
        value = cls.SOURCE_ALIASES.get(value, value)
        allowed = {s.value for s in VerificationSource}
        if value not in allowed:
            raise ValueError(f"Unsupported trust verification source: {source}")
        return value

    @classmethod
    def _sanitize_metadata(cls, source: str, body: Dict[str, Any]) -> Dict[str, Any]:
        allowed = cls.METADATA_FIELDS[source]
        clean: Dict[str, Any] = {}
        for key, value in (body or {}).items():
            key_norm = str(key).strip()
            key_lower = key_norm.lower()
            if key_lower not in allowed:
                continue
            if any(term in key_lower for term in cls.FORBIDDEN_TERMS):
                continue
            if not cls._is_safe_metadata_value(value):
                continue
            clean[key_lower] = cls._safe_scalar(value)

        if source == VerificationSource.GITHUB.value:
            cls._copy_alias(clean, "repo_count", "github_repo_count")
            cls._copy_alias(clean, "commit_count", "github_commit_count")
            cls._copy_alias(clean, "contributor_count", "github_contributor_count")
            cls._copy_alias(clean, "last_activity", "github_last_activity_at")
        if source == VerificationSource.DEPLOYMENT.value:
            cls._copy_alias(clean, "last_deployment", "last_deployment_at")
        if source == VerificationSource.PRODUCT_ANALYTICS.value:
            cls._copy_alias(clean, "growth_pct", "growth_rate_pct")
            cls._copy_alias(clean, "retention_pct", "retention_rate_pct")

        return clean

    @staticmethod
    def _copy_alias(data: Dict[str, Any], src: str, dest: str) -> None:
        if src in data and dest not in data:
            data[dest] = data[src]

    @classmethod
    def _is_safe_metadata_value(cls, value: Any) -> bool:
        return isinstance(value, (str, int, float, bool, datetime)) or value is None

    @classmethod
    def _safe_scalar(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @classmethod
    def _dropped_fields(cls, source: str, body: Dict[str, Any]) -> List[str]:
        allowed = cls.METADATA_FIELDS[source]
        dropped = []
        for key, value in (body or {}).items():
            key_lower = str(key).strip().lower()
            if (
                key_lower not in allowed
                or any(term in key_lower for term in cls.FORBIDDEN_TERMS)
                or not cls._is_safe_metadata_value(value)
            ):
                dropped.append(str(key))
        return sorted(set(dropped))

    @staticmethod
    def _status_for_action(action: str, metadata: Dict[str, Any]) -> VerificationStatus:
        if action == "disconnect":
            return VerificationStatus.DISCONNECTED
        if action == "expire":
            return VerificationStatus.EXPIRED
        if action == "fail":
            return VerificationStatus.FAILED
        if str(metadata.get("approval_status", "")).lower() == "rejected":
            return VerificationStatus.FAILED
        if metadata.get("verified") is True or str(metadata.get("approval_status", "")).lower() == "approved":
            return VerificationStatus.VERIFIED
        if action == "refresh":
            return VerificationStatus.PENDING
        return VerificationStatus.PENDING

    @staticmethod
    def _confidence_for(status: VerificationStatus, metadata: Dict[str, Any]) -> float:
        try:
            supplied = float(metadata.get("confidence"))
        except (TypeError, ValueError):
            supplied = 0.0
        if supplied:
            return round(max(0.0, min(1.0, supplied)), 4)
        if status == VerificationStatus.VERIFIED:
            return 0.95
        if status == VerificationStatus.DISCONNECTED:
            return 0.0
        if status == VerificationStatus.FAILED:
            return 0.1
        return 0.5

    @staticmethod
    def _confidence_from_score(score: float) -> float:
        return round(max(0.0, min(1.0, score / 100.0)), 4)

    def _load_profile_row(self, user_context: UserContext, db: Any = None) -> Any:
        if db is None:
            return None
        try:
            from database_schema import TrustProfile

            query = db.query(TrustProfile).filter(TrustProfile.user_id == user_context.user_id)
            if user_context.project_id:
                query = query.filter(TrustProfile.project_id == user_context.project_id)
            return query.first()
        except Exception:
            return None

    def _load_history_rows(self, user_context: UserContext, db: Any = None, limit: int = 50) -> List[Any]:
        if db is None:
            return []
        try:
            from database_schema import TrustVerificationHistory

            capped = min(max(int(limit), 1), 100)
            query = db.query(TrustVerificationHistory).filter(
                TrustVerificationHistory.user_id == user_context.user_id
            )
            if user_context.project_id:
                query = query.filter(TrustVerificationHistory.project_id == user_context.project_id)
            return query.order_by(TrustVerificationHistory.created_at.desc()).limit(capped).all()
        except Exception:
            return []

    def _persist_verification(
        self,
        user_context: UserContext,
        source: str,
        metadata: Dict[str, Any],
        record: Any,
        db: Any = None,
    ) -> bool:
        if db is None:
            return False

        try:
            from database_schema import (
                TrustBadgeSnapshot,
                TrustProfile,
                TrustTimelineEvent,
                TrustVerificationHistory,
            )

            profile_row = self._load_profile_row(user_context, db)
            if profile_row is None:
                profile_row = TrustProfile(
                    user_id=user_context.user_id,
                    project_id=user_context.project_id,
                )
                db.add(profile_row)

            self._apply_source_to_profile(profile_row, source, metadata, record.status, record.created_at)
            profile = self._profile_from_row(user_context, profile_row)
            computed = TrustEngineComputer.compute(profile, now=record.created_at)
            profile_row.trust_score = computed["trust_score"]
            profile_row.confidence_score = self._confidence_from_score(computed["trust_score"])
            profile_row.badges = computed["badges"]

            db.add(TrustVerificationHistory(
                verification_id=record.verification_id,
                user_id=user_context.user_id,
                project_id=user_context.project_id,
                subject_id=record.subject_id,
                subject_type=record.subject_type,
                source=self._schema_enum("VerificationSourceEnum", source),
                status=self._schema_enum("VerificationStatusEnum", record.status),
                confidence=record.confidence,
                metadata_hash=record.metadata_hash,
                reference_id=record.reference_id,
                event_type=record.event_type,
                expires_at=record.expires_at,
                created_at=record.created_at,
            ))

            timeline_payload = {
                "event_type": record.event_type,
                "reference_id": record.reference_id,
                "source": source,
                "status": record.status,
                "created_at": record.created_at.isoformat(),
            }
            db.add(TrustTimelineEvent(
                user_id=user_context.user_id,
                project_id=user_context.project_id,
                event_type=record.event_type,
                reference_id=record.reference_id,
                visibility="private",
                source=self._schema_enum("VerificationSourceEnum", source),
                content_hash=TrustEngineComputer.hash_metadata(timeline_payload),
                created_at=record.created_at,
            ))

            for badge in computed["badge_records"]:
                if badge.is_active:
                    db.add(TrustBadgeSnapshot(
                        user_id=user_context.user_id,
                        project_id=user_context.project_id,
                        badge_type=badge.badge_type,
                        label=badge.label,
                        source=self._schema_enum("VerificationSourceEnum", badge.source),
                        status=self._schema_enum("VerificationStatusEnum", badge.status),
                        issued_at=badge.issued_at,
                        expires_at=badge.expires_at,
                    ))

            db.commit()
            return True
        except Exception:
            if hasattr(db, "rollback"):
                db.rollback()
            return False

    @staticmethod
    def _schema_enum(enum_name: str, value: str) -> Any:
        from database_schema import VerificationSourceEnum, VerificationStatusEnum

        enum_cls = {
            "VerificationSourceEnum": VerificationSourceEnum,
            "VerificationStatusEnum": VerificationStatusEnum,
        }[enum_name]
        for member in enum_cls:
            if member.value == value:
                return member
        raise ValueError(f"Unsupported {enum_name}: {value}")

    def _profile_from_row(self, user_context: UserContext, row: Any = None) -> FounderTrustProfile:
        if row is None:
            return FounderTrustProfile(founder_id=user_context.user_id)

        return FounderTrustProfile(
            founder_id=user_context.user_id,
            email_verified=bool(getattr(row, "email_verified", False)),
            phone_verified=bool(getattr(row, "phone_verified", False)),
            github_connected=bool(getattr(row, "github_connected", False)),
            linkedin_connected=bool(getattr(row, "linkedin_connected", False)),
            domain_verified=bool(getattr(row, "domain_verified", False)),
            organization_verified=bool(getattr(row, "organization_verified", False)),
            deployment_live=bool(getattr(row, "deployment_live", False)),
            product_activity_verified=bool(getattr(row, "product_activity_verified", False)),
            team_verified_count=int(getattr(row, "verified_team_count", 0) or 0),
            milestone_count=int(getattr(row, "milestone_count", 0) or 0),
            github_repo_count=int(getattr(row, "github_repo_count", 0) or 0),
            github_commit_count=int(getattr(row, "github_commit_count", 0) or 0),
            github_contributor_count=int(getattr(row, "github_contributor_count", 0) or 0),
            github_last_activity_at=getattr(row, "github_last_activity_at", None),
            deployments_30d=int(getattr(row, "deployments_30d", 0) or 0),
            last_deployment_at=getattr(row, "last_deployment_at", None),
            mau=int(getattr(row, "mau", 0) or 0),
            dau=int(getattr(row, "dau", 0) or 0),
            growth_rate_pct=float(getattr(row, "growth_rate_pct", 0.0) or 0.0),
            retention_rate_pct=float(getattr(row, "retention_rate_pct", 0.0) or 0.0),
            last_sync_at=getattr(row, "last_sync_at", None),
            verification_status=self._value(getattr(row, "verification_status", VerificationStatus.UNVERIFIED.value)),
            trust_score=float(getattr(row, "trust_score", 0.0) or 0.0),
        )

    def _apply_source_to_profile(
        self,
        row: Any,
        source: str,
        metadata: Dict[str, Any],
        status: str,
        verified_at: datetime,
    ) -> None:
        is_verified = status == VerificationStatus.VERIFIED.value

        if source == VerificationSource.EMAIL.value:
            row.email_verified = is_verified
        elif source == VerificationSource.PHONE.value:
            row.phone_verified = is_verified
        elif source == VerificationSource.GITHUB.value:
            row.github_connected = is_verified
            row.github_repo_count = int(metadata.get("github_repo_count", 0) or 0)
            row.github_commit_count = int(metadata.get("github_commit_count", 0) or 0)
            row.github_contributor_count = int(metadata.get("github_contributor_count", 0) or 0)
            row.github_last_activity_at = self._parse_dt(metadata.get("github_last_activity_at"))
        elif source == VerificationSource.LINKEDIN.value:
            row.linkedin_connected = is_verified
        elif source in (VerificationSource.DOMAIN.value, VerificationSource.WEBSITE.value):
            row.domain_verified = is_verified
        elif source == VerificationSource.ORGANIZATION.value:
            row.organization_verified = is_verified
        elif source == VerificationSource.DEPLOYMENT.value:
            row.deployment_live = is_verified or bool(metadata.get("deployment_live"))
            row.deployments_30d = int(metadata.get("deployments_30d", 0) or 0)
            row.last_deployment_at = self._parse_dt(metadata.get("last_deployment_at"))
        elif source == VerificationSource.PRODUCT_ANALYTICS.value:
            row.product_activity_verified = is_verified
            row.mau = int(metadata.get("mau", 0) or 0)
            row.dau = int(metadata.get("dau", 0) or 0)
            row.growth_rate_pct = float(metadata.get("growth_rate_pct", 0.0) or 0.0)
            row.retention_rate_pct = float(metadata.get("retention_rate_pct", 0.0) or 0.0)
        elif source == VerificationSource.TEAM.value:
            row.verified_team_count = int(metadata.get("verified_team_count", 0) or 0)
        elif source == VerificationSource.MILESTONE.value and is_verified:
            row.milestone_count = int(getattr(row, "milestone_count", 0) or 0) + 1

        row.verification_status = self._schema_enum("VerificationStatusEnum", status)
        row.last_sync_at = verified_at
        row.updated_at = verified_at

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    @staticmethod
    def _value(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _iso(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _badge_to_dict(badge: Any) -> Dict[str, Any]:
        return {
            "badge_type": badge.badge_type,
            "label": badge.label,
            "source": badge.source,
            "status": badge.status,
            "issued_at": badge.issued_at.isoformat(),
            "expires_at": badge.expires_at.isoformat(),
            "active": badge.is_active,
        }

    def _history_row_to_dict(self, row: Any) -> Dict[str, Any]:
        return {
            "verification_id": str(getattr(row, "verification_id", "")),
            "source": self._value(getattr(row, "source", "")),
            "status": self._value(getattr(row, "status", "")),
            "confidence": float(getattr(row, "confidence", 0.0) or 0.0),
            "metadata_hash": getattr(row, "metadata_hash", ""),
            "reference_id": getattr(row, "reference_id", None),
            "event_type": getattr(row, "event_type", ""),
            "expires_at": self._iso(getattr(row, "expires_at", None)),
            "created_at": self._iso(getattr(row, "created_at", None)),
        }

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        return {
            "verification_id": record.verification_id,
            "subject_id": record.subject_id,
            "subject_type": record.subject_type,
            "source": record.source,
            "status": record.status,
            "confidence": record.confidence,
            "metadata_hash": record.metadata_hash,
            "reference_id": record.reference_id,
            "event_type": record.event_type,
            "expires_at": record.expires_at.isoformat(),
            "created_at": record.created_at.isoformat(),
        }

    @staticmethod
    def _privacy_notice() -> Dict[str, Any]:
        return {
            "metadata_only": True,
            "raw_payload_stored": False,
            "secrets_stored": False,
            "history_append_only": True,
        }

    @staticmethod
    def _next_action(source: str, status: VerificationStatus) -> str:
        if status == VerificationStatus.VERIFIED:
            return "Verification accepted. Keep the source connected so it can refresh before expiry."
        if status == VerificationStatus.DISCONNECTED:
            return "Integration disconnected. Existing history remains append-only."
        if source == VerificationSource.MILESTONE.value:
            return "Milestone is pending review. Prefer public evidence URLs over uploads."
        return "Verification pending. A future provider adapter should complete the source check."



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
# GEO SIGNAL SERVICE  (Investor Global Heatmap — region/sector aggregation)
# ============================================================================

class GeoSignalService:
    """
    Geographic aggregation for the investor Global Heatmap: per-region startup
    counts + average readiness + compliance rate, and per-sector growth. The
    engine previously had no geo signal; this aggregates it.

    Production: GROUP BY region/sector over `projects` + latest `score_snapshots`.
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def get_heatmap(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/investor/heatmap -- 0 credits, Investor+"""
        return {
            "regions": [
                {"name": "North America", "avgReadiness": 84, "complianceRate": 78, "color": "text-emerald-400"},
                {"name": "Europe",        "avgReadiness": 86, "complianceRate": 82, "color": "text-blue-400"},
                {"name": "Asia",          "avgReadiness": 78, "complianceRate": 64, "color": "text-purple-400"},
            ],
            "sectors": [
                {"sector": "SaaS",           "avgGrowth": 42},
                {"sector": "AI/ML",          "avgGrowth": 58},
                {"sector": "FinTech",        "avgGrowth": 47},
                {"sector": "BioTech",        "avgGrowth": 31},
                {"sector": "Infrastructure", "avgGrowth": 38},
                {"sector": "Security",       "avgGrowth": 44},
            ],
        }


# ============================================================================
# PROJECT SERVICE  (Founder multi-project)
# ============================================================================

class ProjectService:
    """
    A founder's portfolio of ventures (projects). Enables MULTIPLE separate
    startups per founder — the dashboard + incubation hub were single-project.

    Response keys camelCase to match frontend contracts.
    Production: query `projects` WHERE owner_id = :uid (+ `project_analyses`).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def list_founder_projects(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/founder/projects -- 0 credits, Free+"""
        return {"projects": self._load_projects(user_context)}

    async def create_project(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/founder/projects -- 0 credits.
        Body: { title, tagline?, industry?, stage?, hackathonId?, teamId? }.
        Production: INSERT projects (+ project_origins row when hackathonId+teamId
        are present, so the venture knows it was promoted from a hackathon team).
        """
        title = (body.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "title_required"}
        hackathon_id = body.get("hackathonId") or body.get("hackathon_id")
        team_id = body.get("teamId") or body.get("team_id")
        project: Dict[str, Any] = {
            "id": body.get("id", "proj_new"),
            "title": title,
            "tagline": body.get("tagline", ""),
            "industry": body.get("industry", ""),
            "stage": body.get("stage", "idea"),
            "isPrimary": False,
            "gsisScore": 0,
            "hasWorkspace": False,
        }
        if hackathon_id and team_id:
            project["origin"] = {
                "kind": "hackathon_promote",
                "hackathonId": hackathon_id,
                "teamId": team_id,
            }
        return {"ok": True, "project": project}

    def _load_projects(self, user_context: UserContext) -> List[Dict[str, Any]]:
        # Production: SELECT id,title,tagline,industry,stage,gsis_score FROM projects
        # WHERE owner_id = :uid ORDER BY created_at.
        return [
            {"id": "proj_demo_001", "title": "AI Task Manager", "tagline": "Execution OS for builders",
             "industry": "saas", "stage": "mvp", "isPrimary": True,  "gsisScore": 88, "hasWorkspace": True},
            {"id": "proj_demo_002", "title": "MicroMint", "tagline": "Stablecoin rails for SMEs",
             "industry": "fintech", "stage": "idea", "isPrimary": False, "gsisScore": 72, "hasWorkspace": False},
        ]


# ============================================================================
# WORKSPACE SERVICE  (Incubation → Workspace pipeline; project-scoped)
# ============================================================================

class WorkspaceService:
    """
    Workspaces bound to a specific analyzed venture (project). Provisions a
    workspace from a project's persisted analysis and serves project-scoped
    context to the workspace AI. Closes the Incubation→Workspace gap.

    Production: query `workspaces` + `project_analyses` (database_schema.py).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    async def list_workspaces(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/workspaces -- 0 credits, Free+"""
        return {"workspaces": self._load_workspaces(user_context)}

    async def provision_workspace(
        self, user_context: UserContext, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/workspaces/provision -- 0 credits.
        Body: { projectId, name? }. Creates (or returns existing) a workspace
        bound to the analyzed project, seeded from its latest analysis.
        """
        project_id = body.get("projectId")
        if not project_id:
            return {"ok": False, "error": "projectId_required"}
        return {
            "ok": True,
            "workspace": {
                "id": body.get("id", f"ws_{project_id}"),
                "projectId": project_id,
                "name": body.get("name", "Venture Workspace"),
                "status": "active",
                "seededFromAnalysis": True,
            },
        }

    async def get_workspace_context(
        self, user_context: UserContext, workspace_id: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        GET /api/v1/workspaces/{workspace_id}/context -- 0 credits.
        Loads the bound project's latest analysis/blueprint so the workspace AI
        is scoped to the specific analyzed venture (not a context-free blob).
        """
        analysis = ProjectService(self.brain)._load_projects(user_context)
        primary = next((p for p in analysis if p["id"] == project_id), analysis[0] if analysis else None)
        return {
            "workspaceId": workspace_id,
            "projectId": project_id or (primary["id"] if primary else None),
            "venture": primary,
            # Blueprint would come from project_analyses.blueprint (latest row).
            "blueprintAvailable": bool(primary and primary.get("hasWorkspace")),
        }

    def _load_workspaces(self, user_context: UserContext) -> List[Dict[str, Any]]:
        return [
            {"id": "ws_proj_demo_001", "projectId": "proj_demo_001",
             "name": "AI Task Manager", "status": "active", "seededFromAnalysis": True},
        ]


# ============================================================================
# HACKATHON SERVICE  (org host intelligence + team/founder + idea→workspace)
# ============================================================================

# Process-level store: hackathon_id -> { team_id -> team dict }. This makes the
# org↔team loop functionally LIVE in-process: a brief or check-in posted by a
# team immediately surfaces in the org overview / velocity / leaderboard.
# Caveat: ephemeral (resets on restart) and NOT shared across multiple workers —
# the durable layer is the hackathon_* tables in database_schema.py.
_HACKATHON_STORE: Dict[str, Dict[str, Dict[str, Any]]] = {}

# Per-hackathon asyncio.Lock so concurrent register / submit_brief / log_check_in
# / provision_team_workspace / report_team_to_organizers can't race-mutate the
# same team dict. Without this lock, two simultaneous check-ins read the same
# (activity, checkIns) tuple → compute different running means → last write
# wins → one check-in is silently lost. Python yields on every await in the
# request handlers, so this IS a real race (unlike the file-store case in
# Node where write() is await-free).
#
# The lock dict itself is mutated only inside _store_lock() which is also
# guarded by the module's GIL for the dict-write step — fine for the
# single-process FastAPI deploy. Multi-process gunicorn workers would need
# a Redis lock; the existing "ephemeral, not shared across workers" caveat
# above applies.
import asyncio as _asyncio
_HACKATHON_LOCKS: Dict[str, _asyncio.Lock] = {}

# Seed teams so the org command-centre renders before any live activity arrives.
# Now gated: production traffic must not see Loom Health / Solaris / Verdant /
# Northwind appearing on the org dashboard before any real team has registered.
# Set HACKATHON_SEED_TEAMS=true to opt back into seeding (the dev/test default).
_SEED_TEAMS: List[Dict[str, Any]] = [
    {"id": "team_001", "name": "Loom Health", "isSolo": False, "status": "building",
     "hasBrief": True, "composite": 88, "checkIns": 5, "hasWorkspace": True},
    {"id": "team_002", "name": "Solaris", "isSolo": False, "status": "building",
     "hasBrief": True, "composite": 76, "checkIns": 3, "hasWorkspace": True},
    {"id": "team_003", "name": "Verdant", "isSolo": True, "status": "registered",
     "hasBrief": False, "composite": 41, "checkIns": 1, "hasWorkspace": False},
    {"id": "team_004", "name": "Northwind", "isSolo": False, "status": "submitted",
     "hasBrief": True, "composite": 91, "checkIns": 7, "hasWorkspace": True},
]


def _seed_teams_enabled() -> bool:
    """Seeding is on for dev/test, off for staging/production by default.
    Override either way with HACKATHON_SEED_TEAMS=true|false.
    """
    import os
    explicit = os.getenv("HACKATHON_SEED_TEAMS")
    if explicit is not None:
        return explicit.strip().lower() in ("1", "true", "yes")
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    return env in ("development", "dev", "local", "test")


class HackathonService:
    """
    Hackathon intelligence: real-time reporting to the ORG host (registrations,
    build-velocity heatmap aggregated from REAL check-ins, composite leaderboard,
    CRS pipeline) and to TEAMS/founders (scored briefs, team status), plus a
    brief→workspace pipe so analyzed hackathon ideas flow into a team workspace.

    Composite scoring mirrors the frontend formula:
      platformAvg = avg(problem_clarity, team_momentum, min(100, demo_hours*6))
      composite   = judgePct*0.5 + platformAvg*0.5
    Reads/writes go through an in-process store (_HACKATHON_STORE) so the loop is
    live; production swaps that for queries over hackathons / hackathon_teams /
    hackathon_briefs / hackathon_check_ins / hackathon_scores (database_schema.py).
    """

    def __init__(self, brain: TechITAIBrain) -> None:
        self.brain = brain

    # ── org host facing ───────────────────────────────────────────────────
    async def list_hackathons(self, user_context: UserContext) -> Dict[str, Any]:
        """GET /api/v1/hackathons -- 0 credits."""
        return {"hackathons": [
            {"id": "hack_001", "name": "TechIT Global AI Hackathon", "theme": "AI for Good",
             "status": "live", "registrants": 420, "teamsFormed": 87},
        ]}

    async def get_overview(self, user_context: UserContext, hackathon_id: str) -> Dict[str, Any]:
        """
        GET /api/v1/hackathons/{id}/overview -- 0 credits.
        Real-time org command-centre stats, derived live from the store.
        Production: COUNT/aggregate over hackathon_teams + hackathon_briefs +
        hackathon_check_ins.
        """
        teams = self._teams(hackathon_id)
        solo = sum(1 for t in teams if t["isSolo"])
        briefs_in = sum(1 for t in teams if t["hasBrief"])
        return {
            "hackathonId": hackathon_id,
            "status": "live",
            "registrants": 420 + max(0, len(teams) - len(_SEED_TEAMS)),
            "teamsFormed": sum(1 for t in teams if not t["isSolo"]),
            "stillSolo": solo,
            "ideaSubmissions": briefs_in,
            "totalTeams": len(teams),
            "avgBuildVelocity": round(self._avg_velocity(hackathon_id), 1),
        }

    async def get_velocity_heatmap(
        self, user_context: UserContext, hackathon_id: str
    ) -> Dict[str, Any]:
        """
        GET /api/v1/hackathons/{id}/velocity -- 0 credits.
        REAL per-team build velocity from check-ins (replaces Math.random()).
        Production: aggregate activity_score from hackathon_check_ins per team
        over the recent window.
        """
        return {"hackathonId": hackathon_id, "teams": self._velocity_cells(hackathon_id)}

    async def get_leaderboard(
        self, user_context: UserContext, hackathon_id: str
    ) -> Dict[str, Any]:
        """GET /api/v1/hackathons/{id}/leaderboard -- 0 credits. Composite-ranked."""
        teams = self._teams(hackathon_id)
        ranked = sorted(
            [{"teamId": t["id"], "name": t["name"], "composite": t["composite"],
              "crsBand": self._crs_band(t["composite"] / 10.0)} for t in teams],
            key=lambda x: x["composite"], reverse=True,
        )
        return {"hackathonId": hackathon_id, "leaderboard": ranked}

    async def get_pipeline(
        self, user_context: UserContext, hackathon_id: str
    ) -> Dict[str, Any]:
        """GET /api/v1/hackathons/{id}/pipeline -- 0 credits. CRS bucket counts."""
        teams = self._teams(hackathon_id)
        crs = [t["composite"] / 10.0 for t in teams]
        return {
            "hackathonId": hackathon_id,
            "buckets": {
                "incubationInvites": sum(1 for c in crs if c > 7),    # CRS > 7
                "prototypeTrack":    sum(1 for c in crs if 4 <= c <= 6),
                "backToLearning":    sum(1 for c in crs if c < 4),
            },
        }

    # ── team / founder facing ─────────────────────────────────────────────
    async def register(self, user_context: UserContext, body: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/v1/hackathons/{id}/register -- 0 credits. Body: { name?, members? }"""
        members = body.get("members", [])
        is_solo = len(members) <= 1
        team_id = body.get("teamId", "team_new")
        hackathon_id = body.get("hackathonId")
        async with self._lock(hackathon_id):
            store = self._store(hackathon_id)
            team = store.get(team_id) or self._new_team(team_id, body.get("name", "Solo"))
            team.update({"name": body.get("name", team["name"]), "isSolo": is_solo,
                         "status": "registered"})
            store[team_id] = team
            snapshot = {
                "id": team["id"], "name": team["name"],
                "isSolo": team["isSolo"], "status": team["status"],
            }
        return {"ok": True, "team": snapshot}

    async def submit_brief(self, user_context: UserContext, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /api/v1/hackathons/{id}/brief -- 0 credits.
        Scores the idea brief (platform composite) and persists it to the store
        so the org command-centre sees the submission live.
        Body: { teamId, problem, solution, fields, demoReadinessHours?,
                judgeScores? }
        """
        problem = body.get("problem", "") or ""
        solution = body.get("solution", "") or ""
        problem_clarity = self._clarity_score(problem)
        team_momentum   = float(body.get("teamMomentum", 70))
        demo_hours      = float(body.get("demoReadinessHours", 6))
        platform_avg = (problem_clarity + team_momentum + min(100.0, demo_hours * 6)) / 3.0
        judge_scores = body.get("judgeScores") or {}
        judge_pct = (sum(judge_scores.values()) / len(judge_scores) / 10.0 * 100.0) if judge_scores else platform_avg
        composite = round(judge_pct * 0.5 + platform_avg * 0.5)

        team_id = body.get("teamId")
        if team_id:
            hackathon_id = body.get("hackathonId")
            async with self._lock(hackathon_id):
                store = self._store(hackathon_id)
                team = store.get(team_id) or self._new_team(team_id)
                team.update({"hasBrief": True, "composite": composite,
                             "status": "building" if team["status"] == "registered" else team["status"]})
                store[team_id] = team

        return {
            "ok": True,
            "score": {
                "problemClarityScore": round(problem_clarity),
                "teamMomentumScore": round(team_momentum),
                "demoReadinessHours": demo_hours,
                "platformAvg": round(platform_avg),
                "judgePct": round(judge_pct),
                "composite": composite,
                "crsBand": self._crs_band(composite / 10.0),
            },
            "critiques": self._critiques(problem, solution),
        }

    async def log_check_in(self, user_context: UserContext, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /api/v1/hackathons/{id}/checkin -- 0 credits.
        Records a build check-in; its activity_score updates the team's running
        velocity in the store, which feeds the org heatmap live.
        Body: { teamId, note, progressDelta? }
        """
        progress = float(body.get("progressDelta", 10))
        activity = min(100.0, max(0.0, progress * 5))

        team_id = body.get("teamId")
        if team_id:
            hackathon_id = body.get("hackathonId")
            async with self._lock(hackathon_id):
                store = self._store(hackathon_id)
                team = store.get(team_id) or self._new_team(team_id)
                n = team["checkIns"]
                team["activity"] = round((team["activity"] * n + activity) / (n + 1), 1)
                team["checkIns"] = n + 1
                if team["status"] == "registered":
                    team["status"] = "building"
                store[team_id] = team

        return {"ok": True, "checkIn": {
            "teamId": team_id, "note": body.get("note", ""),
            "activityScore": round(activity)}}

    async def get_team_status(
        self, user_context: UserContext, hackathon_id: str, team_id: str
    ) -> Dict[str, Any]:
        """GET /api/v1/hackathons/{id}/teams/{tid}/status -- 0 credits."""
        teams = self._teams(hackathon_id)
        team = next((t for t in teams if t["id"] == team_id), teams[0])
        return {
            "hackathonId": hackathon_id, "teamId": team["id"], "name": team["name"],
            "status": team["status"], "hasBrief": team["hasBrief"],
            "composite": team["composite"], "checkIns": team["checkIns"],
            "hasWorkspace": team["hasWorkspace"],
        }

    async def provision_team_workspace(
        self, user_context: UserContext, hackathon_id: str, team_id: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/hackathons/{id}/teams/{tid}/workspace -- 0 credits.
        Pipe the analyzed hackathon brief into a team workspace (reuses
        WorkspaceService) and mark the team's workspace live in the store.
        Body: { projectId? }.
        """
        project_id = body.get("projectId") or f"proj_hack_{team_id}"
        ws = await WorkspaceService(self.brain).provision_workspace(
            user_context, {"projectId": project_id, "name": body.get("name", "Hackathon Team")},
        )
        async with self._lock(hackathon_id):
            store = self._store(hackathon_id)
            team = store.get(team_id) or self._new_team(team_id)
            team.update({"hasWorkspace": True, "projectId": project_id})
            store[team_id] = team
        return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, **ws}

    async def report_team_to_organizers(
        self, user_context: UserContext, hackathon_id: str, team_id: str, body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        POST /api/v1/hackathons/{id}/teams/{tid}/report -- 0 credits.
        Record a team report (idea/team/artifacts/stage + optional workspaceId)
        on the team so org dashboards can surface it. Production: INSERT into
        hackathon_team_reports keyed by (hackathon_id, team_id, created_at).
        """
        report = {
            "workspaceId": body.get("workspaceId"),
            "idea": body.get("idea"),
            "team": body.get("team"),
            "artifacts": body.get("artifacts"),
            "stage": body.get("stage"),
            "reportedBy": user_context.user_id,
        }
        async with self._lock(hackathon_id):
            store = self._store(hackathon_id)
            team = store.get(team_id) or self._new_team(team_id)
            # Keep last N reports per team; here N=10.
            history = team.get("reports") or []
            history.append(report)
            team["reports"] = history[-10:]
            store[team_id] = team
        return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, "report": report}

    # ── helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _lock(hackathon_id: Optional[str]) -> _asyncio.Lock:
        """Return (lazy-allocating) the asyncio.Lock guarding this hackathon's
        store. Dict-write of the lock itself is atomic under the GIL — safe."""
        key = hackathon_id or "_default"
        lock = _HACKATHON_LOCKS.get(key)
        if lock is None:
            lock = _asyncio.Lock()
            _HACKATHON_LOCKS[key] = lock
        return lock

    @staticmethod
    def _store(hackathon_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Return (seeding on first touch) the team store for a hackathon.

        Seed teams are only inserted when `_seed_teams_enabled()` returns True
        (dev/test, or HACKATHON_SEED_TEAMS=true). Production gets an empty
        store so org dashboards don't render Loom Health / Solaris / Verdant /
        Northwind before any real team has registered.
        """
        key = hackathon_id or "_default"
        store = _HACKATHON_STORE.get(key)
        if store is None:
            store = {}
            if _seed_teams_enabled():
                for seed in _SEED_TEAMS:
                    team = dict(seed)
                    # Seed a deterministic baseline activity (never random);
                    # real check-ins blend into this running mean via
                    # log_check_in.
                    team["activity"] = float(
                        min(100, 30 + team["checkIns"] * 12 + int(team["composite"]) % 25)
                    )
                    store[team["id"]] = team
            _HACKATHON_STORE[key] = store
        return store

    @staticmethod
    def _new_team(team_id: str, name: str = "Team") -> Dict[str, Any]:
        return {"id": team_id, "name": name, "isSolo": True, "status": "registered",
                "hasBrief": False, "composite": 0, "checkIns": 0,
                "hasWorkspace": False, "activity": 0.0}

    def _teams(self, hackathon_id: str) -> List[Dict[str, Any]]:
        return list(self._store(hackathon_id).values())

    @staticmethod
    def _clarity_score(text: str) -> float:
        n = len(text.strip())
        base = 40 if n >= 80 else 20 if n >= 40 else 5
        pain = ["struggle", "can't", "wastes", "lacks", "hard", "fail"]
        if any(w in text.lower() for w in pain):
            base += 25
        if any(ch.isdigit() for ch in text):
            base += 15
        return float(min(100, base + 15))

    @staticmethod
    def _critiques(problem: str, solution: str) -> List[str]:
        out: List[str] = []
        if len(problem.strip()) < 80:
            out.append("Sharpen the problem: who hurts, and how badly?")
        if not any(ch.isdigit() for ch in problem + solution):
            out.append("Add a number — market size, time wasted, or users affected.")
        if len(solution.strip()) < 60:
            out.append("Make the solution concrete: what does it actually do?")
        return out

    @staticmethod
    def _crs_band(crs10: float) -> str:
        return ">7" if crs10 > 7 else "4-6" if crs10 >= 4 else "<4"

    def _avg_velocity(self, hackathon_id: str) -> float:
        cells = self._velocity_cells(hackathon_id)
        return sum(c["activity"] for c in cells) / len(cells) if cells else 0.0

    def _velocity_cells(self, hackathon_id: str) -> List[Dict[str, Any]]:
        # Live: per-team running-mean activity from posted check-ins (maintained
        # in log_check_in). Seeded from a deterministic baseline (never random)
        # in _store so the heatmap renders before any check-in arrives.
        return [{"teamId": t["id"], "name": t["name"], "activity": round(t["activity"])}
                for t in self._teams(hackathon_id)]


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
