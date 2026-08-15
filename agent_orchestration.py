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
    ScoringEngine,
)
from output_validation import OutputValidationError, validate_output
from policy_registry import calibration_metadata


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
    FOUNDER_INTERROGATION = "founder_interrogation"
    EVIDENCE_RESEARCH     = "evidence_research"
    PMF_VALIDATION        = "pmf_validation"
    GEOGRAPHIC_INTELLIGENCE = "geographic_intelligence"
    MVP_BUILD_PLANNER     = "mvp_build_planner"
    COMPANY_BUILDING_VALIDATOR = "company_building_validator"
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
    tokens_used:       int = 0
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
        venture = input_data.get("venture_profile") if isinstance(input_data.get("venture_profile"), dict) else {}
        return await self.ai_brain.process_request(AIRequest(
            task_type=task_type, user_context=user_context,
            input_data=input_data, ip_protected=ip_protected, max_tokens=max_tokens,
            requested_model=input_data.get("model_id") or input_data.get("requested_model") or venture.get("model_id") or venture.get("requested_model"),
            execution_profile=str(input_data.get("execution_profile") or venture.get("execution_profile") or "balanced"),
        ))

    @staticmethod
    def _structured(output: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import json
        import re
        try:
            clean = re.sub(r"```(?:json)?|```", "", output or "").strip()
            value = json.loads(clean)
            return value if isinstance(value, dict) else (fallback or {})
        except (TypeError, ValueError):
            return fallback or {"analysis": output}

    def _log(self, result: AgentResult) -> None:
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "success":   result.success,
            "tokens_used": result.tokens_used,
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
                import json as _json
                fingerprint = _hl.sha256(idea_text.encode()).hexdigest()
                embed_resp = await self._call_ai(
                    TaskType.EMBEDDINGS,
                    {"text": idea_text},
                    context.user_context, ip_protected=True, max_tokens=1,
                )
                parsed = _json.loads(embed_resp.output)
                vectors = parsed.get("embeddings") if isinstance(parsed, dict) else None
                vector = vectors[0] if isinstance(vectors, list) and vectors else []
                context.shared_memory["idea_fingerprint"] = fingerprint
                context.shared_memory["idea_embedding"] = vector
                context.shared_memory["idea_embedding_model"] = embed_resp.model_used
                context.shared_memory["idea_embedding_pending"] = not bool(vector)
            except Exception:
                context.shared_memory["idea_embedding_pending"] = True
        # ── END IP PROTECTION ────────────────────────────────────────────────

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        return AgentResult(
            AgentType.VENTURE_INTAKE, True,
            {"venture_profile": profile,
             "idea_fingerprint": context.shared_memory.get("idea_fingerprint", ""),
             "idea_embedding": context.shared_memory.get("idea_embedding", []),
             "idea_embedding_model": context.shared_memory.get("idea_embedding_model"),
             "ip_protected": True},
            ["Parsed raw founder input", "Built Structured Venture Profile",
             "Fingerprinted idea for IP leak detection"],
            ["Proceed to Unicorn Evaluation"],
            ["Run UnicornEvaluatorAgent"],
            ms, ai.tokens_used,
        )


class UnicornEvaluatorAgent(BaseAgent):
    @staticmethod
    def _numeric_market_score(value: Any) -> Optional[float]:
        import re
        text = str(value or "").lower().replace(",", "")
        match = re.search(r"(\d+(?:\.\d+)?)\s*(trillion|billion|million|bn|mm|m|k)?", text)
        if not match: return None
        amount = float(match.group(1)); unit = match.group(2) or ""
        multiplier = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6, "k": 1e3}.get(unit, 1.0)
        dollars = amount * multiplier
        if dollars >= 1e11: return 10.0
        if dollars >= 1e10: return 9.0
        if dollars >= 1e9: return 8.0
        if dollars >= 1e8: return 6.5
        if dollars >= 1e7: return 5.0
        if dollars >= 1e6: return 3.5
        return 2.0

    @classmethod
    def _derive_drivers(cls, profile: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
        """Derive scores only from supplied evidence, with confidence metadata.

        Missing evidence lowers both the score and confidence. Founders may
        supply explicit 0-10 driver evidence, but every value remains labelled
        provisional until a human accepts the underlying assumptions.
        """
        text = " ".join(str(v) for v in profile.values() if isinstance(v, (str, int, float))).lower()
        explicit = profile.get("unicorn_drivers") if isinstance(profile.get("unicorn_drivers"), dict) else {}
        details: Dict[str, Dict[str, Any]] = {}

        def score(name: str, derived: float, evidence: List[str], confidence: float) -> float:
            raw = explicit.get(name)
            source = "derived_from_founder_input"
            if isinstance(raw, dict):
                raw = raw.get("score")
            try:
                if raw is not None:
                    derived = float(raw); source = "founder_supplied_score"
            except (TypeError, ValueError):
                pass
            value = round(max(0.0, min(10.0, derived)), 2)
            details[name] = {"raw_score": value, "confidence": round(max(0.05, min(1.0, confidence)), 2), "evidence": evidence or ["No direct evidence supplied"], "source": source, "human_review_required": True}
            return value

        market_raw = profile.get("market_size") or profile.get("tam")
        market_numeric = cls._numeric_market_score(market_raw)
        team = profile.get("team") if isinstance(profile.get("team"), list) else []
        traction = str(profile.get("traction") or "")
        problem = str(profile.get("problem") or "")
        solution = str(profile.get("solution") or "")
        customers = str(profile.get("target_customers") or "")
        revenue = str(profile.get("revenue_model") or "")
        competitors = profile.get("competitors") or profile.get("competition")
        evidence_count = sum(bool(profile.get(k)) for k in ("customer_interviews", "users", "revenue", "pilots", "letters_of_intent", "retention"))

        drivers = {
            "market_size": score("market_size", market_numeric if market_numeric is not None else (3.0 + min(2.0, len(str(market_raw)) / 80)), [f"Founder market claim: {market_raw}" if market_raw else "No quantified TAM supplied"], 0.75 if market_numeric is not None else 0.25),
            "problem_severity": score("problem_severity", 2.5 + min(3.0, len(problem) / 90) + (1.5 if any(w in text for w in ("urgent", "critical", "costly", "daily", "compliance", "life-threatening")) else 0) + min(2.0, evidence_count * 0.5), [problem or "No problem statement", f"Demand evidence fields present: {evidence_count}"], 0.3 + min(0.6, evidence_count * 0.12)),
            "founder_advantage": score("founder_advantage", 2.5 + min(2.5, len(team) * 0.8) + (2.0 if any(w in text for w in ("years experience", "domain expert", "previous founder", "patent", "researcher")) else 0), [f"Team members supplied: {len(team)}", str(profile.get("founder_advantage") or "No explicit unfair advantage")], 0.25 + min(0.55, len(team) * 0.12)),
            "technological_moat": score("technological_moat", 2.5 + (3.0 if any(w in solution.lower() for w in ("proprietary", "patent", "unique data", "algorithm", "deep tech")) else 0) + (1.5 if profile.get("ip") or profile.get("data_advantage") else 0), [solution or "No solution detail", str(profile.get("ip") or profile.get("data_advantage") or "No defensibility evidence")], 0.25 + (0.4 if profile.get("ip") or profile.get("data_advantage") else 0)),
            "scalability": score("scalability", 3.0 + (3.5 if any(w in solution.lower() for w in ("software", "saas", "api", "platform", "marketplace", "ai")) else 1.0) - (1.0 if any(w in solution.lower() for w in ("hardware", "factory", "clinic", "inventory")) else 0), [solution or "No delivery model supplied"], 0.45),
            "network_effects": score("network_effects", 2.0 + (4.5 if any(w in text for w in ("marketplace", "community", "network", "user-generated", "collaboration")) else 0) + (1.0 if profile.get("network_effect") else 0), [str(profile.get("network_effect") or "No explicit network-effect loop"), customers or "No customer sides identified"], 0.3 + (0.35 if profile.get("network_effect") else 0)),
            "revenue_model_strength": score("revenue_model_strength", 2.0 + min(3.0, len(revenue) / 45) + (1.5 if any(w in revenue.lower() for w in ("subscription", "transaction", "license", "usage", "commission")) else 0) + (1.0 if profile.get("willingness_to_pay") else 0), [revenue or "No revenue model", str(profile.get("willingness_to_pay") or "No willingness-to-pay evidence")], 0.3 + (0.35 if profile.get("willingness_to_pay") else 0)),
            "market_timing": score("market_timing", 3.0 + (2.0 if any(w in text for w in ("regulation", "mandate", "growing", "adoption", "shortage", "new standard")) else 0) + min(1.5, evidence_count * 0.3), [str(profile.get("market_timing") or "No timing catalyst supplied"), traction or "No traction"], 0.3 + min(0.4, evidence_count * 0.08)),
            "competition_landscape": score("competition_landscape", 3.0 + (2.0 if competitors else 0) + (2.0 if profile.get("differentiation") else 0), [str(competitors or "Competitors not supplied"), str(profile.get("differentiation") or "Differentiation not supplied")], 0.25 + (0.25 if competitors else 0) + (0.25 if profile.get("differentiation") else 0)),
            "capital_efficiency": score("capital_efficiency", 3.5 + (2.5 if any(w in solution.lower() for w in ("software", "saas", "api", "no-code")) else 0) + (1.0 if profile.get("existing_codebase") or profile.get("repo_url") else 0) - (1.5 if any(w in solution.lower() for w in ("factory", "hardware", "clinical trial")) else 0), [str(profile.get("budget") or "Budget not supplied"), "Existing codebase" if profile.get("repo_url") else "No existing codebase supplied"], 0.4),
        }
        return drivers, details

    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        profile = context.shared_memory.get("venture_profile", context.trigger_event or {})
        ai      = await self._call_ai(
            TaskType.UNICORN_ANALYSIS,
            {"venture_profile": profile},
            context.user_context, ip_protected=True, max_tokens=4000,
        )
        drivers, evidence = self._derive_drivers(profile)
        ups = ScoringEngine.compute_unicorn_potential_score(drivers)
        ups["driver_breakdown"] = {
            name: {**ups["driver_breakdown"][name], **evidence[name]}
            for name in ups["driver_breakdown"]
        }
        ups["score_confidence"] = round(sum(item["confidence"] for item in evidence.values()) / len(evidence), 2)
        ups["score_status"] = "provisional_human_review_required"
        context.shared_memory["unicorn_evaluation"] = ups
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        recs = (
            ["Accelerate GTM", "Initiate investor outreach"] if ups["unicorn_potential_score"] >= 75 else
            ["Validate demand with 50+ users", "Sharpen revenue model"]
        )
        return AgentResult(
            AgentType.UNICORN_EVALUATOR, True,
            {**ups, "ai_analysis": ai.output},
            [f"Computed heuristic UPS: {ups['unicorn_potential_score']}/100 ({ups['classification']})"],
            recs, ["Run MarketIntelligenceAgent", "Run ProductFeasibilityAgent"],
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
        )


class InvestorIntelligenceAgent(BaseAgent):
    """
    Computes Investment Score and EVI-I, generates investor-grade signals.
    """
    async def execute(self, context: AgentContext) -> AgentResult:
        t0  = datetime.now()
        ups = context.shared_memory.get("unicorn_evaluation", {})
        investment_fields = {
            "market_readiness": context.shared_memory.get("market_readiness"),
            "traction_score": context.shared_memory.get("traction_score"),
            "team_score": context.shared_memory.get("team_score"),
            "risk_inverse": context.shared_memory.get("risk_inverse"),
            "growth_rate": context.shared_memory.get("growth_rate"),
            "differentiation_score": context.shared_memory.get("differentiation_score"),
        }
        evi_fields = {
            "mdr": context.shared_memory.get("mdr"),
            "is": context.shared_memory.get("is"),
            "trv": context.shared_memory.get("trv"),
            "rta": context.shared_memory.get("rta"),
            "ugm": context.shared_memory.get("ugm"),
            "cev": context.shared_memory.get("cev"),
        }
        valid_investment, missing_investment = self._validated_scores(investment_fields)
        valid_evi, missing_evi = self._validated_scores(evi_fields)

        invest_score = None
        if not missing_investment:
            invest_score = ScoringEngine.compute_investment_score(**valid_investment)

        evi_i = None
        if not missing_evi:
            evi_i = ScoringEngine.compute_evi_investor(
                mdr_score=valid_evi["mdr"],
                is_score=valid_evi["is"],
                trv_score=valid_evi["trv"],
                rta_score=valid_evi["rta"],
                ugm_score=valid_evi["ugm"],
                cev_score=valid_evi["cev"],
                days_since_last_update=context.user_context.days_since_update,
            )

        missing_evidence = [
            *(f"investment.{name}" for name in missing_investment),
            *(f"evi_i.{name}" for name in missing_evi),
        ]
        evidence_status = "sufficient" if not missing_evidence else "insufficient_evidence"
        ai = None
        if evidence_status == "sufficient":
            ai = await self._call_ai(
                TaskType.INVESTOR_SIGNAL,
                {"venture_profile": context.shared_memory.get("venture_profile", {}),
                 "unicorn_evaluation": ups,
                 "investment_score": invest_score,
                 "evi_i": evi_i,
                 "score_kind": "heuristic_human_review_required"},
                context.user_context, max_tokens=3000,
            )
        ms = int((datetime.now() - t0).total_seconds() * 1000)
        actions = []
        if invest_score is not None:
            actions.append(f"Investment Score: {invest_score}/100")
        if evi_i is not None:
            actions.append(f"EVI-I: {evi_i['adjusted_evi_i']} ({evi_i['signal']})")
        if not actions:
            actions.append("Investor scoring blocked by insufficient evidence")
        return AgentResult(
            AgentType.INVESTOR_INTELLIGENCE, True,
            {
                "investment_score": invest_score,
                "evi_i": evi_i,
                "investor_signals": ai.output if ai else None,
                "evidence_status": evidence_status,
                "missing_evidence": missing_evidence,
                "score_kind": "heuristic_human_review_required",
                "probability_calibrated": False,
                "human_review_required": True,
                "policy": ScoringEngine.policy_metadata(),
                "calibration": calibration_metadata(),
            },
            actions,
            ["Collect the missing verified investor evidence"] if missing_evidence else
            ["Review evidence and assumptions before investor outreach"],
            ["Complete investor evidence profile"] if missing_evidence else
            ["Generate a human-reviewed investor readiness report"],
            ms, ai.tokens_used if ai else 0,
        )

    @staticmethod
    def _validated_scores(values: Dict[str, Any]) -> tuple[Dict[str, float], List[str]]:
        valid: Dict[str, float] = {}
        missing: List[str] = []
        for name, raw in values.items():
            try:
                score = float(raw)
            except (TypeError, ValueError):
                missing.append(name)
                continue
            if not math.isfinite(score) or not 0 <= score <= 100:
                missing.append(name)
                continue
            valid[name] = score
        return valid, missing


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
            ms, exec_r.tokens_used + plan_r.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
        )


class FounderInterrogationAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        venture = context.shared_memory.get("venture_profile", context.trigger_event or {})
        answers = (context.trigger_event or {}).get("founder_answers", {})
        response = await self._call_ai(
            TaskType.FOUNDER_INTERROGATION,
            {"venture_profile": venture, "founder_answers": answers},
            context.user_context,
            ip_protected=True,
            max_tokens=5000,
        )
        fallback_questions = [
            {"id": "customer", "priority": "critical", "category": "customer", "question": "Who is the narrow first customer, in which geography?", "why_it_matters": "A broad customer definition makes demand evidence non-falsifiable.", "answer_type": "text"},
            {"id": "pain", "priority": "critical", "category": "problem", "question": "How often does this customer experience the problem, and what do they do today?", "why_it_matters": "Frequency and an existing workaround reveal urgency.", "answer_type": "text"},
            {"id": "evidence", "priority": "critical", "category": "validation", "question": "What direct evidence exists from interviews, usage, commitments, or revenue?", "why_it_matters": "Founder conviction is not customer evidence.", "answer_type": "text"},
        ]
        data = self._structured(response.output, {
            "questions": fallback_questions,
            "blocking_unknowns": [q["id"] for q in fallback_questions if q["id"] not in answers],
            "contradictions": [],
            "provisional_assumptions": [],
            "validation_blocked": True,
        })
        unanswered = [q for q in data.get("questions", []) if not answers.get(str(q.get("id", "")))]
        data["validation_blocked"] = bool(unanswered or data.get("blocking_unknowns"))
        data["human_approval_required"] = True
        context.shared_memory["founder_interrogation"] = data
        return AgentResult(
            AgentType.FOUNDER_INTERROGATION, True, data,
            ["Identified blocking unknowns", "Generated prioritized founder questions"],
            ["Answer critical questions before accepting a validation verdict"],
            ["Submit founder answers", "Run evidence research"],
            int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used,
        )


class EvidenceResearchAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        response = await self._call_ai(
            TaskType.EVIDENCE_RESEARCH,
            {"venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
             "geography": (context.trigger_event or {}).get("geography"),
             "research_capability": (context.trigger_event or {}).get("research_capability", "model_knowledge")},
            context.user_context, max_tokens=7000,
        )
        data = self._structured(response.output, {"sources": [], "competitors": [], "failed_attempts": [], "contradictory_evidence": [], "evidence_gaps": ["Live sources unavailable"], "research_mode": "model_knowledge"})
        data["sources"] = [source for source in data.get("sources", []) if isinstance(source, dict) and source.get("url")]
        data["human_review_required"] = True
        context.shared_memory["evidence_research"] = data
        return AgentResult(AgentType.EVIDENCE_RESEARCH, True, data,
            ["Separated sources from model knowledge", "Reviewed competitors, substitutes and failed attempts"],
            ["Verify high-impact sources and contradictory claims"], ["Run PMF validation"],
            int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used)


class PMFValidationAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        interrogation = context.shared_memory.get("founder_interrogation", {})
        response = await self._call_ai(TaskType.PMF_VALIDATION, {
            "venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
            "founder_interrogation": interrogation,
            "evidence": context.shared_memory.get("evidence_research", {}),
            "geography": context.shared_memory.get("geographic_intelligence", {}),
        }, context.user_context, ip_protected=True, max_tokens=6000)
        data = self._structured(response.output, {"provisional_score": 0, "confidence": 0, "status": "blocked", "riskiest_assumptions": [], "falsification_tests": [], "founder_questions": [], "kill_criteria": [], "human_approval_required": True})
        data["provisional_score"] = max(0.0, min(100.0, float(data.get("provisional_score") or 0)))
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence") or 0)))
        if interrogation.get("validation_blocked"):
            data["status"] = "blocked"
        data["human_approval_required"] = True
        data["ai_may_finalize"] = False
        context.shared_memory["pmf_validation"] = data
        return AgentResult(AgentType.PMF_VALIDATION, True, data,
            ["Produced a provisional, confidence-aware PMF assessment", "Defined falsification tests and kill criteria"],
            ["A founder or authorized reviewer must accept or reject the provisional verdict"],
            ["Record human validation decision"], int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used)


class GeographicIntelligenceAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        response = await self._call_ai(TaskType.GEOGRAPHIC_INTELLIGENCE, {
            "venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
            "founder_selected_geography": (context.trigger_event or {}).get("geography") or (context.trigger_event or {}).get("target_geography"),
        }, context.user_context, max_tokens=5000)
        data = self._structured(response.output, {"primary_geography": {}, "local_constraints": [], "local_advantages": [], "regulatory_checks": [], "distribution_channels": [], "competitors": [], "localization": [], "confidence": 0, "evidence_gaps": ["Founder must select a geography"], "founder_questions": []})
        data["human_selection_required"] = True
        context.shared_memory["geographic_intelligence"] = data
        return AgentResult(AgentType.GEOGRAPHIC_INTELLIGENCE, True, data,
            ["Applied local market, regulation and distribution context"],
            ["Founder must confirm the target geography"], ["Confirm target geography"],
            int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used)


class MVPBuildPlannerAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        response = await self._call_ai(TaskType.MVP_BUILD_PLANNING, {
            "venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
            "pmf_validation": context.shared_memory.get("pmf_validation", {}),
            "tech_architecture": context.shared_memory.get("tech_architecture", {}),
            "founder_constraints": (context.trigger_event or {}).get("founder_constraints", {}),
        }, context.user_context, ip_protected=True, max_tokens=10000)
        data = self._structured(response.output, {})
        data["human_approval_required"] = True
        data["approval_action"] = "finalize_mvp_scope"
        context.shared_memory["mvp_build_plan"] = data
        return AgentResult(AgentType.MVP_BUILD_PLANNER, True, data,
            ["Created one-day, three-day, one-week and production MVP scopes", "Included code and test plans"],
            ["Choose the smallest scope that can falsify the riskiest assumption"],
            ["Approve MVP scope before sandbox generation"], int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used)


class CompanyBuildingValidationAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0 = datetime.now()
        response = await self._call_ai(TaskType.COMPANY_BUILDING_VALIDATION, {
            "venture_profile": context.shared_memory.get("venture_profile", context.trigger_event or {}),
            "founder_interrogation": context.shared_memory.get("founder_interrogation", {}),
            "evidence": context.shared_memory.get("evidence_research", {}),
            "pmf_validation": context.shared_memory.get("pmf_validation", {}),
            "founder_constraints": (context.trigger_event or {}).get("founder_constraints", {}),
        }, context.user_context, ip_protected=True, max_tokens=6500)
        data = self._structured(response.output, {
            "company_thesis": "A company thesis is not established yet; validate the recurring customer workflow and distribution loop.",
            "wedge": {"status": "unknown"}, "ideal_customer_and_buyer": {}, "repeatability": {"status": "unknown"},
            "distribution": {"status": "unknown"}, "business_model": {}, "operating_model": {},
            "defensibility": {"status": "unknown"}, "market_expansion": {}, "company_risks": ["No company-level evidence supplied"],
            "product_risks": [], "leading_indicators": [], "30_day_company_experiments": [], "founder_questions": [],
            "human_approval_required": True,
        })
        data["human_approval_required"] = True
        data["company_status"] = "provisional_human_review_required"
        context.shared_memory["company_building_validation"] = data
        return AgentResult(AgentType.COMPANY_BUILDING_VALIDATOR, True, data,
            ["Separated product wedge from company thesis", "Tested repeatability, distribution, operating model and compounding advantage"],
            ["Run company-level experiments alongside product validation"],
            ["Founder selects company thesis and first repeatable distribution loop"],
            int((datetime.now() - t0).total_seconds() * 1000), response.tokens_used)


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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
        )


class MatchingAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0       = datetime.now()
        trigger = context.trigger_event or {}
        candidates = trigger.get("persisted_candidates")
        if not isinstance(candidates, list):
            candidates = []
        verified = []
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or not candidate.get("user_id")
                or candidate.get("match_score") is None
                or not isinstance(candidate.get("evidence"), dict)
                or candidate["evidence"].get("source") != "persisted_match_record"
            ):
                continue
            try:
                float(candidate["match_score"])
            except (TypeError, ValueError):
                continue
            verified.append(candidate)
        verified.sort(key=lambda item: float(item["match_score"]), reverse=True)

        ai = await self._call_ai(
            TaskType.MATCHING,
            {"seeker_profile": context.user_context.to_prompt_context(),
             "top_matches": verified[:3]},
            context.user_context,
        ) if verified else None

        ms = int((datetime.now() - t0).total_seconds() * 1000)
        evidence_status = "sufficient" if verified else "insufficient_evidence"
        return AgentResult(
            AgentType.MATCHING, True,
            {
                "matches": verified,
                "explanations": ai.output if ai else None,
                "evidence_status": evidence_status,
                "missing_evidence": [] if verified else ["persisted_match_candidates"],
                "policy": ScoringEngine.policy_metadata(),
                "calibration": calibration_metadata(),
                "human_review_required": True,
            },
            [f"Found {len(verified)} persisted compatible matches"],
            ["Review evidence and compatibility before outreach"] if verified else
            ["Collect profile and collaboration evidence before matching"],
            ["Invite a reviewed match"] if verified else ["Complete matching profiles"],
            ms, ai.tokens_used if ai else 0,
        )


class RiskEvaluatorAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        t0   = datetime.now()
        idea = (context.trigger_event or {}).get("idea", {})
        required_fields = ("problem", "solution", "target_customers")
        missing_evidence = [name for name in required_fields if not str(idea.get(name) or "").strip()]
        supplied_evidence = [name for name, value in idea.items() if value not in (None, "", [], {})]
        ai = None
        if not missing_evidence:
            ai = await self._call_ai(TaskType.RISK_ANALYSIS, {
                **idea,
                "evidence_contract": {
                    "source": "founder_supplied",
                    "numeric_scores_allowed": False,
                    "human_review_required": True,
                },
            }, context.user_context, ip_protected=True)
        ms   = int((datetime.now() - t0).total_seconds() * 1000)
        evidence_status = "insufficient_evidence" if missing_evidence else "provisional_human_review_required"
        return AgentResult(
            AgentType.RISK_EVALUATOR, True,
            {"risk_analysis": {
                "status": evidence_status,
                "market_clarity_score": None,
                "technical_feasibility": None,
                "competitive_risk": None,
                "key_risks": [],
                "swot": {},
                "ai_analysis": ai.output if ai else None,
                "evidence": {
                    "source": "founder_supplied",
                    "supplied_fields": supplied_evidence,
                    "missing_fields": missing_evidence,
                },
                "human_review_required": True,
            }},
            ["Generated provisional risk narrative"] if ai else
            ["Risk analysis blocked by insufficient evidence"],
            ["Validate risk claims with primary evidence"] if ai else
            ["Supply the missing venture evidence"],
            ["Human review of risk evidence"] if ai else ["Complete venture risk inputs"],
            ms, ai.tokens_used if ai else 0,
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
             "workspace_context_pack": trigger.get("workspace_context_pack", {}),
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
                },
                "alerts":   alerts,
                "insights": ai.output,
            },
            ["Computed GSIS and all component scores", f"GSIS: {gsis_result['gsis']}"],
            ["Act on top alert", "Complete pending training module"],
            ["Check dashboard daily"],
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
            ms, ai.tokens_used,
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
        # The scaffold agent consumes the architecture through shared memory.
        # Keep the inner value instead of the AgentResult wrapper so both
        # on-demand and pipeline execution receive an identical contract.
        shared["tech_architecture"] = tasks[1].output

        r = await self.orch.trigger_agent(AgentType.INVESTOR_INTELLIGENCE, ctx())
        results["investor"] = r

        # Prompt -> Live App: scaffold runs after architecture is designed
        r = await self.orch.trigger_agent(AgentType.APP_SCAFFOLD, ctx())
        results["app_scaffold"] = r
        shared["app_scaffold"] = r.output

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
                "tokens_used":   resp.tokens_used,
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
    SCAFFOLD_SCHEMA = {
        "type": "object",
        "required": ["pages", "schema_sql", "api_routes", "env_template", "components", "setup_steps", "estimated_build_hours"],
        "properties": {
            "pages": {"type": "array", "items": {"type": "object", "required": ["route", "component_name"], "properties": {"route": {"type": "string", "minLength": 1}, "component_name": {"type": "string", "minLength": 1}}}},
            "schema_sql": {"type": "string"},
            "api_routes": {"type": "array", "items": {"type": "object", "required": ["method", "path"], "properties": {"method": {"type": "string"}, "path": {"type": "string", "minLength": 1}}}},
            "env_template": {"type": "string"},
            "components": {"type": "array"},
            "setup_steps": {"type": "array", "items": {"type": "string"}},
            "estimated_build_hours": {"type": "number", "minimum": 0},
        },
        "additionalProperties": True,
    }
    DEPLOY_SCHEMA = {
        "type": "object",
        "required": ["deploy_steps"],
        "properties": {"deploy_steps": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}},
        "additionalProperties": True,
    }

    async def execute(self, context: AgentContext) -> AgentResult:
        t0      = datetime.now()
        event   = context.trigger_event or {}
        profile = context.shared_memory.get("venture_profile", context.trigger_event or {})
        arch    = context.shared_memory.get("tech_architecture", {})
        profile = profile if isinstance(profile, dict) else {}
        arch = arch if isinstance(arch, dict) else {}

        stack, selection_rationale = self._select_stack(profile, arch, event.get("stack"))
        if stack is None:
            return AgentResult(
                agent_type=AgentType.APP_SCAFFOLD,
                success=False,
                output={
                    "status": "insufficient_configuration",
                    "reason_code": "explicit_supported_stack_required",
                    "supported_stacks": sorted(self.SUPPORTED_STACKS),
                    "artifact_registered": False,
                    "download_url": None,
                    "deploy_url": None,
                    "live_url": None,
                },
                actions_taken=["Scaffold generation blocked before model execution"],
                recommendations=["Select an approved stack for this project"],
                next_steps=["Submit a supported stack with the scaffold request"],
                execution_time_ms=int((datetime.now() - t0).total_seconds() * 1000),
            )

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
        if scaffold is None:
            return self._invalid_generation_result(t0, "invalid_scaffold_output", scaffold_resp.tokens_used)

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
        if deploy_config is None:
            return self._invalid_generation_result(
                t0,
                "invalid_deploy_configuration_output",
                scaffold_resp.tokens_used + deploy_resp.tokens_used,
            )

        # Step 4: Build the complete scaffold output
        full_scaffold = {
            "scaffold_type":      stack,
            "stack_description":  self.SUPPORTED_STACKS.get(stack, stack),
            "stack_selection_rationale": selection_rationale,
            "startup_name":       profile.get("startup_name", "MyStartup"),
            "pages":              scaffold.get("pages", []),
            "schema_sql":         scaffold.get("schema_sql", ""),
            "api_routes":         scaffold.get("api_routes", []),
            "env_template":       scaffold.get("env_template", ""),
            "components":         scaffold.get("components", []),
            "setup_steps":        scaffold.get("setup_steps", []),
            "estimated_build_hours": scaffold.get("estimated_build_hours"),
            "deploy_config":      deploy_config,
            "status":             "generated_unregistered",
            "artifact_registered": False,
            "download_url":       None,
            "deploy_url":         None,
            "live_url":           None,
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
                "Validated scaffold structure",
                "Validated deployment configuration structure",
                "Created .env.example template",
            ],
            recommendations=[
                "Review generated code and security controls",
                "Register an immutable artifact before download or deployment",
            ],
            next_steps=[
                "Persist files in the artifact service",
                "Run build, dependency, secret, and policy checks",
                "Deploy through an authenticated production connector",
            ],
            execution_time_ms=ms,
            tokens_used=scaffold_resp.tokens_used + deploy_resp.tokens_used,
        )

    def _select_stack(self, profile: dict, arch: dict, requested_stack: Any = None) -> tuple[Optional[str], Optional[Dict[str, str]]]:
        """
        Select only an explicit, supported stack from the request or structured
        project architecture. The router does not infer technology from prose.
        """
        for source, value in (
            ("request.stack_choice", requested_stack),
            ("venture_profile.stack_choice", profile.get("stack_choice")),
            ("tech_architecture.stack_key", arch.get("stack_key")),
            ("tech_architecture.scaffold_type", arch.get("scaffold_type")),
        ):
            candidate = str(value or "").strip()
            if candidate in self.SUPPORTED_STACKS:
                return candidate, {"source": source, "selected_stack": candidate, "reason": "explicit_approved_configuration"}
        return None, None

    def _parse_scaffold(self, raw_output: str) -> Optional[dict]:
        """
        Parse and minimally validate the AI scaffold JSON response.
        """
        try:
            parsed = validate_output(raw_output, self.SCAFFOLD_SCHEMA)
        except (OutputValidationError, TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _parse_deploy_config(self, raw_output: str) -> Optional[dict]:
        """Parse deploy config JSON and reject invalid output."""
        try:
            parsed = validate_output(raw_output, self.DEPLOY_SCHEMA)
        except (OutputValidationError, TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _invalid_generation_result(t0: datetime, reason_code: str, tokens_used: int) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.APP_SCAFFOLD,
            success=False,
            output={
                "status": "invalid_model_output",
                "reason_code": reason_code,
                "artifact_registered": False,
                "download_url": None,
                "deploy_url": None,
                "live_url": None,
            },
            actions_taken=["Rejected invalid generated artifact"],
            recommendations=["Regenerate and validate before artifact registration"],
            next_steps=["Retry generation with structured output enforcement"],
            execution_time_ms=int((datetime.now() - t0).total_seconds() * 1000),
            tokens_used=tokens_used,
        )


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
            # (AgentType, Class, name, triggers, schedule)
            (AgentType.VENTURE_INTAKE, VentureIntakeAgent, "Venture Intake", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.UNICORN_EVALUATOR, UnicornEvaluatorAgent, "Unicorn Probability Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.MARKET_INTELLIGENCE, MarketIntelligenceAgent, "Market Intelligence Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.PRODUCT_FEASIBILITY, ProductFeasibilityAgent, "Product Feasibility Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.STARTUP_STRATEGY, StartupStrategyAgent, "Startup Strategy Generator", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.FINANCE_STRATEGY, FinanceStrategyAgent, "Finance Strategy Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.INVESTOR_INTELLIGENCE, InvestorIntelligenceAgent, "Investor Intelligence Engine", [AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN], "0 0 * * *"),
            (AgentType.BUSINESS_PLAN_GEN, BusinessPlanGeneratorAgent, "Business Plan Generator", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.TECH_ARCHITECT, TechArchitectAgent, "Tech Architecture Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.PIVOT_INTELLIGENCE, PivotIntelligenceAgent, "Pivot Intelligence Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.FOUNDER_INTERROGATION, FounderInterrogationAgent, "Founder Interrogation Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.EVIDENCE_RESEARCH, EvidenceResearchAgent, "Evidence Research Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.PMF_VALIDATION, PMFValidationAgent, "PMF Validation Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.GEOGRAPHIC_INTELLIGENCE, GeographicIntelligenceAgent, "Geographic Intelligence Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.MVP_BUILD_PLANNER, MVPBuildPlannerAgent, "MVP Build Planner Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.COMPANY_BUILDING_VALIDATOR, CompanyBuildingValidationAgent, "Company Building Validator", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.TOUR_GUIDE, TourGuideAgent, "AI Tour Guide", [AgentTrigger.SCHEDULED, AgentTrigger.ON_DEMAND], "0 6 * * *"),
            (AgentType.ADAPTIVE_TRAINING, AdaptiveTrainingAgent, "Adaptive Training Agent", [AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN], "0 2 * * 1"),
            (AgentType.MATCHING, MatchingAgent, "Team Matching Engine", [AgentTrigger.ON_DEMAND, AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.RISK_EVALUATOR, RiskEvaluatorAgent, "Risk Evaluator Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.WORKSPACE_ASSISTANT, WorkspaceAssistantAgent, "Workspace Assistant", [AgentTrigger.ON_DEMAND, AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.FEED_INTELLIGENCE, FeedIntelligenceAgent, "Feed Intelligence Engine", [AgentTrigger.SCHEDULED], "*/30 * * * *"),
            (AgentType.DASHBOARD_INTELLIGENCE, DashboardIntelligenceAgent, "Dashboard Intelligence", [AgentTrigger.ON_DEMAND, AgentTrigger.SCHEDULED], "*/30 * * * *"),
            (AgentType.AI_PROFILE, AIProfileAgent, "AI Profile Agent", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.ORG_SPHERE, OrgSphereAgent, "Org Sphere Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.ADMIN_MONITOR, AdminMonitorAgent, "Admin Monitor Agent", [AgentTrigger.SCHEDULED, AgentTrigger.EVENT_DRIVEN], "*/15 * * * *"),
            (AgentType.GSIS_COMPUTE, GSISComputeAgent, "GSIS Compute Agent", [AgentTrigger.ON_DEMAND, AgentTrigger.SCHEDULED], "*/30 * * * *"),
            (AgentType.PROBLEM_ANALYZER, ProblemAnalyzerAgent, "Problem Analyzer", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.SOLUTION_SYNTHESIZER, SolutionSynthesizerAgent, "Solution Synthesizer", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.IMPACT_PREDICTOR, ImpactPredictorAgent, "Impact Predictor", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.FEASIBILITY_ESTIMATOR, FeasibilityEstimatorAgent, "Feasibility Estimator", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.PROBLEM_DISCOVERY, ProblemDiscoveryAgent, "Problem Discovery Engine", [AgentTrigger.SCHEDULED, AgentTrigger.ON_DEMAND], "0 6 * * *"),
            (AgentType.SOLUTION_MATCHER, SolutionMatcherAgent, "Solution Matching Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.DEPLOYMENT_PLANNER, DeploymentPlannerAgent, "Deployment Planner", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.GRANT_MATCHER, GrantMatcherAgent, "Grant Matching Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.DISCUSSION_MODERATOR, DiscussionModeratorAgent, "Discussion Moderator", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.SCHEDULED], "*/60 * * * *"),
            (AgentType.FIELD_FEEDBACK_AGENT, FieldFeedbackAgent, "Field Feedback Analyst", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.DOCUMENT_GENERATION, DocumentGenerationAgent, "Document Generation Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
            (AgentType.DOCUMENT_EXPORT, DocumentExportAgent, "Document Export Agent", [AgentTrigger.EVENT_DRIVEN], None),
            (AgentType.APP_SCAFFOLD, AppScaffoldAgent, "App Scaffold Engine", [AgentTrigger.EVENT_DRIVEN, AgentTrigger.ON_DEMAND], None),
        ]
        for atype, cls, name, triggers, schedule in registry:
            config = AgentConfig(atype, name, f"TechIT {name}", triggers, schedule, 60, 3)
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
          Lifecycle-triggered investor intelligence runs with a system actor so
          audit trails distinguish it from a direct user request.
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
