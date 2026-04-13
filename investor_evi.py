"""
TECHIT -- EXECUTION VELOCITY INDEX FOR INVESTOR INTELLIGENCE (EVI-I)
====================================================================
Module: investor_evi.py
Layer:  Investor Intelligence Engine -- Signal Computation Layer

Purpose
───────
The EVI-I answers the one question every institutional investor asks
before writing a cheque:

    "Is this founding team executing fast enough to be worth watching?"

It is entirely distinct from the founder-facing EVI in ai_router_core.py.
The founder EVI measures personal momentum for daily coaching.
The EVI-I translates a startup's raw execution behaviour into a
structured, decay-adjusted, investor-grade signal.

EVI-I integrates into:
  - Global Startup Intelligence Score (GSIS)  -- 15% weight via EVI component
  - Investor Interest Score (IIS)             -- amplified by EVI-I signal
  - WCRS marketplace ranking                  -- adjusted score input
  - Investor deal flow dashboards
  - Watchlist threshold alerts
  - AI-generated due-diligence summaries
  - investor_evi_snapshots DB table

Formula
───────
  EVI-I = (0.25*MDR + 0.20*IS + 0.15*TRV + 0.20*RTA + 0.10*UGM + 0.10*CEV)

  Anti-gaming decay (identical to WCRS):
    DecayFactor  = e^(−0.02 × days_since_last_update)
    EVI-I_adj    = EVI-I_raw × DecayFactor

Dimension Weights
─────────────────
  MDR  25%  Milestone Delivery Rate        -- are they shipping what they promised?
  IS   20%  Iteration Speed                -- how fast do they learn from feedback?
  TRV  15%  Team Response Velocity         -- do they respond quickly to the market?
  RTA  20%  Revenue Traction Acceleration  -- is revenue compounding?
  UGM  10%  User Growth Momentum           -- is the user base growing faster?
  CEV  10%  Capital Efficiency Velocity    -- more output per dollar over time?

Signal Classifications
──────────────────────
  85–100  Exceptional Velocity  🔥  high-conviction buy signal
  70–84   Strong Velocity       🚀  worth active tracking
  55–69   Moderate Velocity     📈  monitor, not urgent
  40–54   Slow Velocity         ⏳  re-evaluate in 60 days
   0–39   Stalled               🔴  investor flag raised
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# SIGNAL CLASSIFICATION
# ============================================================================

class EVIInvestorSignal(Enum):
    EXCEPTIONAL = "exceptional_velocity"
    STRONG      = "strong_velocity"
    MODERATE    = "moderate_velocity"
    SLOW        = "slow_velocity"
    STALLED     = "stalled"


# ============================================================================
# INPUT DATA STRUCTURES
# ============================================================================

@dataclass
class MilestoneDeliveryData:
    """
    Sourced from: workspace milestones + readiness_tracker tables.
    """
    milestones_committed_30d:   int
    milestones_delivered_30d:   int
    avg_days_to_complete:       float
    late_deliveries_count:      int
    milestone_quality_score:    float   # 0–10, AI-assessed


@dataclass
class IterationSpeedData:
    """
    Sourced from: workspace code commits, product changelog, AI output logs.
    """
    product_versions_shipped_30d: int
    avg_feedback_to_fix_days:     float
    feature_cycle_days:           float
    pivots_executed_90d:          int    # 1 = decisive; 3+ = instability flag


@dataclass
class TeamResponseData:
    """
    Sourced from: workspace activity logs, chat logs, event_logs.
    """
    avg_investor_response_hours:   float
    avg_collaborator_response_hrs: float
    platform_session_frequency:    float   # sessions per week
    checkin_consistency_pct:       float   # 0–100


@dataclass
class RevenueTractionData:
    """
    Sourced from: financial data, Stripe integrations.
    """
    mrr_current:          float
    mrr_30d_ago:          float
    mrr_90d_ago:          float
    paying_customers_now: int
    paying_customers_30d: int
    avg_revenue_per_user: float
    churn_rate_pct:       float   # 0–100


@dataclass
class UserGrowthData:
    """
    Sourced from: product analytics, beta testing records.
    """
    total_users_now:      int
    total_users_30d_ago:  int
    total_users_90d_ago:  int
    dau_wau_ratio:        float   # 0–1
    week1_retention_pct:  float   # 0–100
    organic_pct:          float   # 0–100


@dataclass
class CapitalEfficiencyData:
    """
    Sourced from: financial data, funding records.
    """
    total_raised_usd:          float
    monthly_burn_usd:          float
    runway_months:             float
    revenue_per_dollar_raised: float   # ARR / total_raised
    team_size:                 int
    revenue_per_employee:      float


@dataclass
class EVIInvestorInput:
    """Complete input bundle assembled by InvestorIntelligenceAgent."""
    project_id:             str
    project_name:           str
    industry:               str
    stage:                  str
    days_since_last_update: int
    milestone_data:  MilestoneDeliveryData
    iteration_data:  IterationSpeedData
    response_data:   TeamResponseData
    revenue_data:    RevenueTractionData
    user_data:       UserGrowthData
    capital_data:    CapitalEfficiencyData
    computed_at:     datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# EVI-I RESULT
# ============================================================================

@dataclass
class EVIInvestorResult:
    """Full EVI-I output returned to investors and stored in investor_evi_snapshots."""
    project_id:      str
    project_name:    str
    # Dimension scores
    mdr_score:       float
    is_score:        float
    trv_score:       float
    rta_score:       float
    ugm_score:       float
    cev_score:       float
    # Composite
    raw_evi_i:       float
    decay_factor:    float
    adjusted_evi_i:  float
    # Signal
    signal:          EVIInvestorSignal
    signal_label:    str
    signal_emoji:    str
    # Trend
    evi_trend:       str      # accelerating / steady / decelerating / stalled
    trend_delta:     float
    # Narrative
    headline:        str
    strengths:       List[str]
    red_flags:       List[str]
    watch_items:     List[str]
    # Risk
    velocity_risk:   str      # low / medium / high / critical
    # Meta
    computed_at:     datetime = field(default_factory=datetime.utcnow)
    data_freshness:  str      = "current"


# ============================================================================
# EVI-I SCORING ENGINE
# ============================================================================

class EVIInvestorEngine:
    """
    Computes EVI-I from six independent sub-dimensions.
    Each sub-dimension scorer returns (score_0_100, strengths, flags).
    """

    WEIGHTS = {"mdr": 0.25, "is_": 0.20, "trv": 0.15, "rta": 0.20, "ugm": 0.10, "cev": 0.10}

    SIGNAL_TIERS = [
        (85, 100, EVIInvestorSignal.EXCEPTIONAL, "Exceptional Velocity",  "🔥"),
        (70,  84, EVIInvestorSignal.STRONG,      "Strong Velocity",       "🚀"),
        (55,  69, EVIInvestorSignal.MODERATE,    "Moderate Velocity",     "📈"),
        (40,  54, EVIInvestorSignal.SLOW,        "Slow Velocity",         "⏳"),
        ( 0,  39, EVIInvestorSignal.STALLED,     "Stalled",               "🔴"),
    ]

    # ── MDR: Milestone Delivery Rate ───────────────────────────────────────

    def score_mdr(
        self, d: MilestoneDeliveryData
    ) -> Tuple[float, List[str], List[str]]:
        """
        Delivery rate    50% -- milestones_delivered / milestones_committed
        On-time rate     30% -- (delivered - late) / delivered
        Quality          20% -- AI-assessed quality score (0–10 -> 0–1)
        """
        strengths: List[str] = []
        flags:     List[str] = []

        if d.milestones_committed_30d == 0:
            dr = 0.0
            flags.append("No milestones committed in last 30 days")
        else:
            dr = min(1.0, d.milestones_delivered_30d / d.milestones_committed_30d)

        otr = (max(0, d.milestones_delivered_30d - d.late_deliveries_count) /
               max(d.milestones_delivered_30d, 1))
        quality = min(10.0, max(0.0, d.milestone_quality_score)) / 10.0

        score = (0.50*dr + 0.30*otr + 0.20*quality) * 100

        if dr >= 0.90:
            strengths.append(f"High delivery rate: {dr*100:.0f}%")
        elif dr < 0.60:
            flags.append(f"Low delivery rate: {dr*100:.0f}% of commitments met")
        if otr < 0.70:
            flags.append(f"{d.late_deliveries_count} late deliveries -- execution discipline concern")
        if d.milestone_quality_score >= 8.0:
            strengths.append(f"High milestone quality: {d.milestone_quality_score}/10")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── IS: Iteration Speed ────────────────────────────────────────────────

    def score_is(
        self, d: IterationSpeedData
    ) -> Tuple[float, List[str], List[str]]:
        """
        Versions shipped  40% -- benchmark: 4+/month = full
        Feedback loop     35% -- benchmark: ≤3 days = full; >14 = 0
        Feature cycle     25% -- benchmark: ≤7 days = full; >30 = 0
        Pivot penalty     −15% if 3+ pivots in 90d
        """
        strengths: List[str] = []
        flags:     List[str] = []

        vs  = min(1.0, d.product_versions_shipped_30d / 4.0)
        fb  = max(0.0, 1.0 - d.avg_feedback_to_fix_days / 14.0)
        fc  = max(0.0, 1.0 - d.feature_cycle_days / 30.0)
        pen = 0.15 if d.pivots_executed_90d >= 3 else 0.0

        if d.pivots_executed_90d >= 3:
            flags.append(f"{d.pivots_executed_90d} pivots in 90 days -- possible lack of conviction")
        elif d.pivots_executed_90d == 1:
            strengths.append("One decisive pivot -- shows market responsiveness")

        score = (0.40*vs + 0.35*fb + 0.25*fc) * 100 * (1.0 - pen)

        if vs >= 0.75:
            strengths.append(f"{d.product_versions_shipped_30d} product versions shipped this month")
        if d.avg_feedback_to_fix_days <= 3:
            strengths.append(f"Fast feedback loop: {d.avg_feedback_to_fix_days:.1f}-day fix cycle")
        if d.avg_feedback_to_fix_days > 10:
            flags.append(f"Slow feedback loop: {d.avg_feedback_to_fix_days:.1f}-day average")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── TRV: Team Response Velocity ────────────────────────────────────────

    def score_trv(
        self, d: TeamResponseData
    ) -> Tuple[float, List[str], List[str]]:
        """
        Investor response  40% -- ≤4h = full; >48h = 0
        Collab response    25% -- ≤8h = full; >72h = 0
        Platform sessions  20% -- ≥7/week = full
        Check-in rate      15% -- 0–100
        """
        strengths: List[str] = []
        flags:     List[str] = []

        inv  = max(0.0, 1.0 - d.avg_investor_response_hours / 48.0)
        col  = max(0.0, 1.0 - d.avg_collaborator_response_hrs / 72.0)
        sess = min(1.0, d.platform_session_frequency / 7.0)
        chk  = d.checkin_consistency_pct / 100.0

        score = (0.40*inv + 0.25*col + 0.20*sess + 0.15*chk) * 100

        if d.avg_investor_response_hours <= 4:
            strengths.append(f"Fast investor response: {d.avg_investor_response_hours:.1f}h avg")
        if d.avg_investor_response_hours > 24:
            flags.append(f"Slow investor response: {d.avg_investor_response_hours:.0f}h -- DD risk")
        if d.checkin_consistency_pct >= 90:
            strengths.append(f"High check-in consistency: {d.checkin_consistency_pct:.0f}%")
        if d.checkin_consistency_pct < 50:
            flags.append(f"Low check-in consistency: {d.checkin_consistency_pct:.0f}%")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── RTA: Revenue Traction Acceleration ────────────────────────────────

    def score_rta(
        self, d: RevenueTractionData
    ) -> Tuple[float, List[str], List[str]]:
        """
        MRR growth 30d   40% -- benchmark: 20% MoM = full
        MRR growth 90d   20% -- trend stability
        Customer growth  25% -- paying customer expansion rate
        Churn penalty    15% -- >5% churn applies penalty (capped −30%)
        """
        strengths: List[str] = []
        flags:     List[str] = []

        mrr30 = ((d.mrr_current - d.mrr_30d_ago) / max(d.mrr_30d_ago, 1)
                 if d.mrr_30d_ago > 0 else (1.0 if d.mrr_current > 0 else 0.0))
        mrr90 = ((d.mrr_current - d.mrr_90d_ago) / max(d.mrr_90d_ago, 1) / 3.0
                 if d.mrr_90d_ago > 0 else mrr30)
        cust  = ((d.paying_customers_now - d.paying_customers_30d) /
                 max(d.paying_customers_30d, 1)
                 if d.paying_customers_30d > 0 else (1.0 if d.paying_customers_now > 0 else 0.0))

        churn_pen = min(0.30, max(0.0, (d.churn_rate_pct - 5.0) * 0.03))

        m30n = min(1.0, max(0.0, mrr30 / 0.20))
        m90n = min(1.0, max(0.0, mrr90 / 0.20))
        cn   = min(1.0, max(0.0, cust  / 0.20))

        score = (0.40*m30n + 0.20*m90n + 0.25*cn) * 100 * (1.0 - churn_pen)

        if mrr30 >= 0.20:
            strengths.append(f"Strong MRR growth: +{mrr30*100:.1f}% MoM")
        if d.mrr_current == 0:
            flags.append("Pre-revenue -- weight this dimension accordingly")
        if d.churn_rate_pct > 10:
            flags.append(f"High churn: {d.churn_rate_pct:.1f}% monthly -- PMF concern")
        if d.churn_rate_pct <= 3 and d.mrr_current > 0:
            strengths.append(f"Low churn: {d.churn_rate_pct:.1f}% -- strong retention signal")
        if d.paying_customers_now > 0 and d.avg_revenue_per_user > 50:
            strengths.append(f"Healthy ARPU: ${d.avg_revenue_per_user:.0f}/customer")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── UGM: User Growth Momentum ──────────────────────────────────────────

    def score_ugm(
        self, d: UserGrowthData
    ) -> Tuple[float, List[str], List[str]]:
        """
        30-day growth    35% -- benchmark: 20% MoM
        90-day trend     20%
        Week-1 retention 25% -- strongest PMF signal
        Organic %        20% -- word-of-mouth proxy
        """
        strengths: List[str] = []
        flags:     List[str] = []

        g30 = ((d.total_users_now - d.total_users_30d_ago) / max(d.total_users_30d_ago, 1)
               if d.total_users_30d_ago > 0 else (1.0 if d.total_users_now > 0 else 0.0))
        g90 = ((d.total_users_now - d.total_users_90d_ago) / max(d.total_users_90d_ago, 1) / 3.0
               if d.total_users_90d_ago > 0 else g30)

        g30n = min(1.0, max(0.0, g30 / 0.20))
        g90n = min(1.0, max(0.0, g90 / 0.20))
        ret  = d.week1_retention_pct / 100.0
        org  = d.organic_pct / 100.0

        score = (0.35*g30n + 0.20*g90n + 0.25*ret + 0.20*org) * 100

        if d.week1_retention_pct >= 40:
            strengths.append(f"Strong week-1 retention: {d.week1_retention_pct:.0f}%")
        if d.week1_retention_pct < 20:
            flags.append(f"Weak week-1 retention: {d.week1_retention_pct:.0f}% -- onboarding gap")
        if d.organic_pct >= 60:
            strengths.append(f"High organic acquisition: {d.organic_pct:.0f}% -- word-of-mouth")
        if g30 >= 0.30:
            strengths.append(f"Strong user growth: +{g30*100:.1f}% in 30 days")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── CEV: Capital Efficiency Velocity ──────────────────────────────────

    def score_cev(
        self, d: CapitalEfficiencyData
    ) -> Tuple[float, List[str], List[str]]:
        """
        Revenue per $ raised  35% -- benchmark: $0.30 ARR per $1 raised
        Runway adequacy       30% -- benchmark: 18+ months
        Revenue per employee  20% -- benchmark: $100K ARR/employee
        Burn efficiency       15% -- monthly revenue / monthly burn ratio
        """
        strengths: List[str] = []
        flags:     List[str] = []

        rpdr   = min(1.0, d.revenue_per_dollar_raised / 0.30)
        runway = min(1.0, max(0.0, d.runway_months / 18.0))
        rpe    = min(1.0, d.revenue_per_employee / 100_000)
        monthly_arr = (d.revenue_per_dollar_raised * d.total_raised_usd / 12
                       if d.total_raised_usd > 0 else 0)
        burn_eff = min(1.0, monthly_arr / max(1, d.monthly_burn_usd) / 0.5)

        score = (0.35*rpdr + 0.30*runway + 0.20*rpe + 0.15*burn_eff) * 100

        if d.runway_months >= 18:
            strengths.append(f"Strong runway: {d.runway_months:.0f} months")
        if d.runway_months < 6:
            flags.append(f"Critical runway: {d.runway_months:.1f} months -- urgent")
        if d.revenue_per_dollar_raised >= 0.20:
            strengths.append(f"Capital-efficient: ${d.revenue_per_dollar_raised:.2f} ARR per $1 raised")
        if monthly_arr > 0 and d.monthly_burn_usd > 0:
            r = monthly_arr / d.monthly_burn_usd
            if r >= 0.8:
                strengths.append(f"Near break-even: revenue covers {r*100:.0f}% of burn")
        return round(max(0.0, min(100.0, score)), 2), strengths, flags

    # ── COMPOSITE ─────────────────────────────────────────────────────────

    def compute(
        self,
        data:           EVIInvestorInput,
        previous_evi_i: Optional[float] = None,
    ) -> EVIInvestorResult:
        """
        Compute the full EVI-I score and return investor-grade signal.

        Parameters
        ──────────
        data            -- Complete EVIInvestorInput bundle
        previous_evi_i  -- EVI-I from 30 days ago (trend computation)

        Returns
        ───────
        EVIInvestorResult -- full signal with narrative ready for investor UI
        """
        all_s: List[str] = []
        all_f: List[str] = []

        mdr, s, f = self.score_mdr(data.milestone_data);  all_s += s; all_f += f
        is_,  s, f = self.score_is(data.iteration_data);   all_s += s; all_f += f
        trv,  s, f = self.score_trv(data.response_data);   all_s += s; all_f += f
        rta,  s, f = self.score_rta(data.revenue_data);    all_s += s; all_f += f
        ugm,  s, f = self.score_ugm(data.user_data);       all_s += s; all_f += f
        cev,  s, f = self.score_cev(data.capital_data);    all_s += s; all_f += f

        raw = (self.WEIGHTS["mdr"]  * mdr + self.WEIGHTS["is_"]  * is_ +
               self.WEIGHTS["trv"]  * trv + self.WEIGHTS["rta"]  * rta +
               self.WEIGHTS["ugm"]  * ugm + self.WEIGHTS["cev"]  * cev)
        raw  = round(min(100.0, max(0.0, raw)), 2)

        decay    = round(math.exp(-0.02 * max(0, data.days_since_last_update)), 6)
        adjusted = round(raw * decay, 2)

        if data.days_since_last_update > 14:
            all_f.append(
                f"Stagnation: {data.days_since_last_update} days without update "
                f"(decay {decay:.3f} -- score -{round((1-decay)*100, 1)}%)"
            )

        sig, label, emoji = self._classify(adjusted)
        trend, delta      = self._trend(adjusted, previous_evi_i)
        risk              = self._risk(adjusted, len(all_f))
        headline          = self._headline(data.project_name, adjusted, sig, data.revenue_data, data.milestone_data)
        watch             = self._watch(raw, adjusted, decay, mdr, rta)

        return EVIInvestorResult(
            project_id=data.project_id, project_name=data.project_name,
            mdr_score=mdr, is_score=is_, trv_score=trv,
            rta_score=rta, ugm_score=ugm, cev_score=cev,
            raw_evi_i=raw, decay_factor=decay, adjusted_evi_i=adjusted,
            signal=sig, signal_label=label, signal_emoji=emoji,
            evi_trend=trend, trend_delta=delta,
            headline=headline,
            strengths=all_s[:5], red_flags=all_f[:5], watch_items=watch,
            velocity_risk=risk,
            computed_at=data.computed_at,
            data_freshness="stale" if data.days_since_last_update > 7 else "current",
        )

    def _classify(self, score: float) -> Tuple[EVIInvestorSignal, str, str]:
        for lo, hi, sig, label, emoji in self.SIGNAL_TIERS:
            if lo <= score <= hi:
                return sig, label, emoji
        return EVIInvestorSignal.STALLED, "Stalled", "🔴"

    def _trend(self, current: float, previous: Optional[float]) -> Tuple[str, float]:
        if previous is None:
            return "no_prior_data", 0.0
        delta = round(current - previous, 2)
        if delta >= 5:   return "accelerating",  delta
        if delta >= -2:  return "steady",         delta
        if delta >= -10: return "decelerating",   delta
        return "stalled", delta

    def _risk(self, score: float, flag_count: int) -> str:
        if score < 40 or flag_count >= 4: return "critical"
        if score < 55 or flag_count >= 3: return "high"
        if score < 70 or flag_count >= 2: return "medium"
        return "low"

    def _headline(
        self,
        name:  str,
        score: float,
        sig:   EVIInvestorSignal,
        rev:   RevenueTractionData,
        ms:    MilestoneDeliveryData,
    ) -> str:
        if sig == EVIInvestorSignal.EXCEPTIONAL:
            return (f"{name} executing at {score:.0f}/100 -- top-quartile velocity. "
                    f"{ms.milestones_delivered_30d} milestones/month, MRR ${rev.mrr_current:,.0f}.")
        if sig == EVIInvestorSignal.STRONG:
            return (f"{name} shows strong execution at {score:.0f}/100. "
                    f"Solid delivery and growing revenue signal early discipline.")
        if sig == EVIInvestorSignal.MODERATE:
            return (f"{name} executing at moderate pace ({score:.0f}/100). "
                    f"Key gaps exist but team is moving.")
        if sig == EVIInvestorSignal.SLOW:
            return (f"{name} below expectations at {score:.0f}/100. "
                    f"Re-evaluate in 60 days.")
        return (f"{name} execution stalled ({score:.0f}/100). Investor caution advised.")

    def _watch(
        self, raw: float, adj: float, decay: float, mdr: float, rta: float
    ) -> List[str]:
        items = []
        if decay < 0.85:
            items.append("Monitor update frequency -- decay penalty active")
        if mdr < 60:
            items.append("Milestone delivery discipline needs improvement before Series A")
        if rta < 40:
            items.append("Revenue acceleration not yet proven -- pre-revenue signals only")
        if raw > adj + 5:
            items.append(f"Score adjusted -{round(raw - adj, 1)} pts due to inactivity decay")
        return items


# ============================================================================
# INVESTOR EVI SERVICE
# ============================================================================

class InvestorEVIService:
    """
    Service layer for computing and surfacing EVI-I to investors.

    API Endpoints served:
      GET  /api/v1/investor/evi/{project_id}           -- latest EVI-I
      GET  /api/v1/investor/evi/top-performers         -- top 20 by EVI-I
      GET  /api/v1/investor/evi/watchlist/{investor_id} -- watchlisted EVI-I
      GET  /api/v1/investor/evi/trend/{project_id}     -- 90-day history
      GET  /api/v1/investor/evi/signals/alerts         -- velocity risk alerts
    """

    def __init__(self) -> None:
        self.engine = EVIInvestorEngine()

    def compute_from_startup(
        self,
        startup_record: Dict[str, Any],
        previous_evi_i: Optional[float] = None,
    ) -> EVIInvestorResult:
        """
        Build EVIInvestorInput from a raw startup DB record and compute EVI-I.
        """
        ms  = startup_record.get("milestones", {})
        it  = startup_record.get("iteration",  {})
        re  = startup_record.get("response",   {})
        rv  = startup_record.get("revenue",    {})
        ug  = startup_record.get("users",      {})
        ca  = startup_record.get("capital",    {})

        data = EVIInvestorInput(
            project_id=startup_record["project_id"],
            project_name=startup_record["project_name"],
            industry=startup_record.get("industry", "Unknown"),
            stage=startup_record.get("stage", "idea"),
            days_since_last_update=startup_record.get("days_since_update", 0),
            milestone_data=MilestoneDeliveryData(
                milestones_committed_30d=ms.get("committed_30d", 0),
                milestones_delivered_30d=ms.get("delivered_30d", 0),
                avg_days_to_complete=ms.get("avg_days_complete", 14.0),
                late_deliveries_count=ms.get("late_count", 0),
                milestone_quality_score=ms.get("quality_score", 5.0),
            ),
            iteration_data=IterationSpeedData(
                product_versions_shipped_30d=it.get("versions_30d", 0),
                avg_feedback_to_fix_days=it.get("feedback_fix_days", 14.0),
                feature_cycle_days=it.get("feature_cycle_days", 21.0),
                pivots_executed_90d=it.get("pivots_90d", 0),
            ),
            response_data=TeamResponseData(
                avg_investor_response_hours=re.get("investor_response_hrs", 24.0),
                avg_collaborator_response_hrs=re.get("collab_response_hrs", 12.0),
                platform_session_frequency=re.get("sessions_per_week", 3.0),
                checkin_consistency_pct=re.get("checkin_pct", 60.0),
            ),
            revenue_data=RevenueTractionData(
                mrr_current=rv.get("mrr_current", 0),
                mrr_30d_ago=rv.get("mrr_30d", 0),
                mrr_90d_ago=rv.get("mrr_90d", 0),
                paying_customers_now=rv.get("customers_now", 0),
                paying_customers_30d=rv.get("customers_30d", 0),
                avg_revenue_per_user=rv.get("arpu", 0),
                churn_rate_pct=rv.get("churn_pct", 5.0),
            ),
            user_data=UserGrowthData(
                total_users_now=ug.get("users_now", 0),
                total_users_30d_ago=ug.get("users_30d", 0),
                total_users_90d_ago=ug.get("users_90d", 0),
                dau_wau_ratio=ug.get("dau_wau", 0.3),
                week1_retention_pct=ug.get("week1_retention", 20.0),
                organic_pct=ug.get("organic_pct", 40.0),
            ),
            capital_data=CapitalEfficiencyData(
                total_raised_usd=ca.get("total_raised", 0),
                monthly_burn_usd=ca.get("monthly_burn", 5000),
                runway_months=ca.get("runway_months", 12),
                revenue_per_dollar_raised=ca.get("rev_per_dollar", 0),
                team_size=ca.get("team_size", 2),
                revenue_per_employee=ca.get("rev_per_employee", 0),
            ),
        )
        return self.engine.compute(data, previous_evi_i)

    def format_for_dashboard(self, result: EVIInvestorResult) -> Dict[str, Any]:
        """Format EVI-I result for the investor-facing deal flow UI."""
        return {
            "project_id":       result.project_id,
            "project_name":     result.project_name,
            "evi_score":        result.adjusted_evi_i,
            "signal":           result.signal_label,
            "signal_emoji":     result.signal_emoji,
            "velocity_risk":    result.velocity_risk,
            "trend":            result.evi_trend,
            "trend_delta":      result.trend_delta,
            "headline":         result.headline,
            "strengths":        result.strengths,
            "red_flags":        result.red_flags,
            "watch_items":      result.watch_items,
            "dimension_scores": {
                "milestone_delivery_rate":       result.mdr_score,
                "iteration_speed":               result.is_score,
                "team_response_velocity":        result.trv_score,
                "revenue_traction_acceleration": result.rta_score,
                "user_growth_momentum":          result.ugm_score,
                "capital_efficiency_velocity":   result.cev_score,
            },
            "decay_info": {
                "decay_factor":     result.decay_factor,
                "raw_before_decay": result.raw_evi_i,
                "adjusted_score":   result.adjusted_evi_i,
                "data_freshness":   result.data_freshness,
            },
            "computed_at": result.computed_at.isoformat(),
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_evi_i() -> None:
    svc = InvestorEVIService()

    startup = {
        "project_id": "proj_healthtech_001", "project_name": "MediConnect Africa",
        "industry": "Healthtech", "stage": "beta", "days_since_update": 3,
        "milestones": {"committed_30d": 8, "delivered_30d": 7, "avg_days_complete": 5.5,
                       "late_count": 1, "quality_score": 8.2},
        "iteration":  {"versions_30d": 4, "feedback_fix_days": 2.5,
                       "feature_cycle_days": 8.0, "pivots_90d": 1},
        "response":   {"investor_response_hrs": 3.5, "collab_response_hrs": 6.0,
                       "sessions_per_week": 9.0, "checkin_pct": 95.0},
        "revenue":    {"mrr_current": 12_500, "mrr_30d": 9_800, "mrr_90d": 5_200,
                       "customers_now": 47, "customers_30d": 35,
                       "arpu": 265.96, "churn_pct": 3.2},
        "users":      {"users_now": 820, "users_30d": 610, "users_90d": 310,
                       "dau_wau": 0.55, "week1_retention": 52.0, "organic_pct": 68.0},
        "capital":    {"total_raised": 250_000, "monthly_burn": 18_000,
                       "runway_months": 14.0, "rev_per_dollar": 0.60,
                       "team_size": 4, "rev_per_employee": 37_500},
    }

    result  = svc.compute_from_startup(startup, previous_evi_i=65.0)
    display = svc.format_for_dashboard(result)

    print("=" * 65)
    print("TECHIT -- EVI FOR INVESTOR INTELLIGENCE")
    print("=" * 65)
    print(f"\n{result.signal_emoji}  {result.project_name}")
    print(f"   EVI-I Score:   {result.adjusted_evi_i}  ({result.signal_label})")
    print(f"   Raw before decay: {result.raw_evi_i}  | Decay: {result.decay_factor}")
    print(f"   Velocity Risk: {result.velocity_risk.upper()}")
    print(f"   Trend:         {result.evi_trend}  ({result.trend_delta:+.1f} pts vs 30d ago)")
    print(f"\n   {result.headline}")
    print(f"\n   Dimension Scores:")
    dims = display["dimension_scores"]
    for k, v in dims.items():
        print(f"     {k:42s} {v:5.1f}/100")
    print(f"\n   Strengths:")
    for s in result.strengths:
        print(f"     ✅ {s}")
    if result.red_flags:
        print(f"\n   Red Flags:")
        for f in result.red_flags:
            print(f"     🚩 {f}")
    if result.watch_items:
        print(f"\n   Watch Items:")
        for w in result.watch_items:
            print(f"     👁  {w}")
    print("=" * 65)


if __name__ == "__main__":
    example_evi_i()
