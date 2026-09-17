"""Deterministic customer-evidence lifecycle and public response service.

This module owns evidence integrity. It deliberately contains no LLM calls:
question drafting and synthesis are separate AI Router tasks that consume the
immutable records produced here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func

from database_schema import (
    CustomerValidationEvent,
    CustomerValidationBssSnapshot,
    CustomerValidationHypothesis,
    CustomerValidationRecommendation,
    CustomerValidationResponse,
    CustomerValidationShare,
    CustomerValidationSession,
    CustomerValidationSynthesis,
    EventLog,
    TrustTimelineEvent,
    VerificationSourceEnum,
    WorkspaceContextPack,
    Project,
)


OBJECTIVES = {
    "problem_discovery", "problem_severity", "existing_alternative_discovery",
    "solution_fit", "product_feedback", "ux_feedback", "willingness_to_pay",
    "pricing_validation", "channel_discovery", "retention", "churn_diagnosis",
    "nps", "feature_prioritization", "market_assumption_validation",
    "customer_segment_validation", "purchase_intent", "switching_behaviour",
}
MODES = {"interview", "survey", "poll", "hybrid"}
STAGES = {"idea", "validation", "mvp", "beta", "launch", "growth"}
ACTIVE_STATES = {"active"}
TERMINAL_STATES = {"completed", "expired"}
QUESTION_TYPES = {"short_text", "long_text", "yes_no", "multiple_choice", "multiple_select", "rating", "likert", "nps", "numeric", "willingness_to_pay", "ranking"}
_RATE_WINDOWS: Dict[str, deque] = defaultdict(deque)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.utcnow()


def _token_for(session_id: Any) -> str:
    secret = os.getenv("CUSTOMER_VALIDATION_TOKEN_SECRET") or os.getenv("JWT_SECRET") or "local-customer-validation-secret"
    sid = str(session_id)
    signature = hmac.new(secret.encode("utf-8"), sid.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{sid}.{signature}"


def stage_questions(stage: str, objective: str, mode: str) -> List[Dict[str, Any]]:
    """Backend-owned baseline questions; an LLM may later draft replacements."""
    stage = stage if stage in STAGES else "idea"
    base = {
        "idea": [
            "Tell us about the last time you experienced this problem.",
            "How often does this happen?",
            "How do you currently handle it?",
            "What does the current approach cost you in time or money?",
        ],
        "validation": [
            "What have you already tried to solve this problem?",
            "What makes the problem urgent or easy to postpone?",
            "Which current alternative works best, and where does it fail?",
            "What evidence would make you switch approaches?",
        ],
        "mvp": [
            "What did you expect to accomplish with the product?",
            "Describe where the workflow was clear or confusing.",
            "Which part was most useful in the last session?",
            "What did you do when the product did not meet your need?",
        ],
        "beta": [
            "How has your usage changed since you first tried the product?",
            "What value would you miss if the product disappeared?",
            "What prevents you from using it more often?",
            "What alternative would you return to?",
        ],
        "launch": [
            "What triggered your decision to try or buy the product?",
            "Which promise matched your actual experience?",
            "What nearly prevented adoption?",
            "How likely are you to recommend it to a colleague?",
        ],
        "growth": [
            "What keeps you using the product today?",
            "What would cause you to reduce or stop usage?",
            "Which additional outcome would justify expanding usage?",
            "Who else in your organisation benefits from the product?",
        ],
    }[stage]
    if objective in {"willingness_to_pay", "pricing_validation"}:
        base = ["What do you currently spend solving this problem?", "Who approves that spending?", "What result makes the cost worthwhile?", "What has stopped you paying for another option?"]
    elif objective == "nps":
        return [{"id": "q1", "question": "How likely are you to recommend this product to a colleague?", "answer_type": "nps", "required": True, "options": []}, {"id": "q2", "question": "What is the main reason for your score?", "answer_type": "long_text", "required": True, "options": []}]
    if mode == "poll": base = base[:1]
    return [{"id": f"q{index + 1}", "question": text, "answer_type": "long_text", "required": True, "options": []} for index, text in enumerate(base)]


def _stage(project: Optional[Project], requested: Any) -> str:
    value = str(requested or getattr(project, "stage", "idea") or "idea").lower()
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return value if value in STAGES else "idea"


def _public_session(row: CustomerValidationSession) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "title": row.title,
        "description": row.description,
        "objective": row.objective,
        "mode": row.mode,
        "stage": row.stage,
        "questions": row.questions or [],
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "status": row.status,
    }


def _session_dict(row: CustomerValidationSession, *, include_token: bool = False) -> Dict[str, Any]:
    result = {
        "id": str(row.id),
        "projectId": str(row.project_id),
        "incubationSessionId": str(row.incubation_session_id) if row.incubation_session_id else None,
        "hypothesisId": str(row.hypothesis_id) if row.hypothesis_id else None,
        "title": row.title,
        "description": row.description,
        "objective": row.objective,
        "mode": row.mode,
        "stage": row.stage,
        "questions": row.questions or [],
        "respondentProfile": row.respondent_profile or {},
        "sourceConfiguration": row.source_configuration or {},
        "targetRespondents": row.target_respondents,
        "status": row.status,
        "configurationLocked": bool(row.configuration_locked),
        "totalResponseCount": row.total_response_count,
        "qualifiedResponseCount": row.qualified_response_count,
        "qualityCounts": row.quality_counts or {},
        "confidenceLevel": row.confidence_level,
        "synthesisStatus": row.synthesis_status,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_token:
        token = _token_for(row.id)
        result["publicToken"] = token
        result["publicUrlPath"] = f"/validate/{token}"
    return result


def _response_dict(row: CustomerValidationResponse) -> Dict[str, Any]:
    return {"id": str(row.id), "answers": row.answers or {}, "source": row.source,
            "submissionKind": row.submission_kind, "quality": row.quality_classification,
            "evidenceStatus": row.evidence_status, "qualityReasons": row.quality_reasons or [],
            "completionPercentage": row.completion_percentage,
            "receivedAt": row.received_at.isoformat() if row.received_at else None}


def _event_dict(row: CustomerValidationEvent) -> Dict[str, Any]:
    return {"id": str(row.id), "eventType": row.event_type, "metadata": row.metadata_json or {},
            "previousHash": row.previous_hash, "eventHash": row.event_hash,
            "createdAt": row.created_at.isoformat() if row.created_at else None}


def _theme_findings(responses: List[CustomerValidationResponse]) -> Dict[str, Any]:
    terms = {
        "manual_workflow": ("manual", "spreadsheet", "paper", "workaround"),
        "cost": ("cost", "expensive", "price", "pay", "budget"),
        "time": ("time", "slow", "hours", "delay"),
        "automation": ("automate", "automation", "integrat"),
    }
    counts = {key: 0 for key in terms}; quotes: Dict[str, List[str]] = {key: [] for key in terms}
    for response in responses:
        text = " ".join(str(value) for value in (response.answers or {}).values()).lower()
        for key, needles in terms.items():
            if any(needle in text for needle in needles):
                counts[key] += 1
                if len(quotes[key]) < 3:
                    actual = next((str(value).strip() for value in (response.answers or {}).values() if any(needle in str(value).lower() for needle in needles)), "")
                    if actual: quotes[key].append(actual[:280])
    total = len(responses)
    recurring = [{"theme": key, "count": count, "share": round(count / total, 3) if total else 0, "quotes": quotes[key]} for key, count in counts.items() if count]
    segment_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for response in responses:
        for key, value in (response.answers or {}).items():
            if str(key).startswith("segment_") and str(value).strip(): segment_counts[str(key)][str(value).strip()] += 1
    segmentation = {key.removeprefix("segment_"): [{"value": value, "count": count} for value, count in values.items() if count >= 3] for key, values in segment_counts.items()}
    segmentation = {key: values for key, values in segmentation.items() if values}
    contradictions = []
    if counts["manual_workflow"] and counts["automation"] and abs(counts["manual_workflow"] - counts["automation"]) <= max(1, total // 3):
        contradictions.append("Respondents describe manual workflows while expressing mixed appetite for automation.")
    return {"recurringPainPoints": sorted(recurring, key=lambda item: item["count"], reverse=True), "qualifiedResponseCount": total, "contradictions": contradictions, "segmentation": segmentation}


def _project_workspace_context(db: Any, row: CustomerValidationSession) -> None:
    pack = db.query(WorkspaceContextPack).filter(WorkspaceContextPack.project_id == row.project_id).order_by(WorkspaceContextPack.version.desc()).first()
    if pack is not None:
        data = dict(pack.context_data or {})
        data["customer_evidence"] = {"source_type": "CUSTOMER_EVIDENCE", "active_sessions": 1 if row.status == "active" else 0, "qualified_responses": row.qualified_response_count, "total_responses": row.total_response_count, "confidence": row.confidence_level, "objective": row.objective, "session_id": str(row.id), "evidence_gaps": ["More qualified responses needed"] if row.qualified_response_count < 10 else []}
        pack.context_data = data


def _project_event(db: Any, row: CustomerValidationSession, event_type: str, metadata: Dict[str, Any]) -> None:
    db.add(EventLog(event_type=f"customer_validation_{event_type}", event_data=metadata, user_id=row.owner_id, project_id=row.project_id))
    if event_type in {"threshold_reached", "synthesis_completed"}:
        db.add(TrustTimelineEvent(user_id=row.owner_id, project_id=row.project_id, event_type=f"customer_validation_{event_type}", reference_id=str(row.id), visibility="private", source=VerificationSourceEnum.MILESTONE, content_hash=_hash(metadata), created_at=_now()))


def _bss_snapshot(db: Any, row: CustomerValidationSession, synthesis: CustomerValidationSynthesis) -> None:
    if row.objective not in {"nps", "ux_feedback", "willingness_to_pay", "pricing_validation", "product_feedback"}:
        return
    responses = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id, CustomerValidationResponse.evidence_status == "qualified").all()
    values = [value for response in responses for value in (response.answers or {}).values()]
    score = None
    if row.objective == "nps":
        values = [int(value) for value in values if str(value).isdigit() and 0 <= int(value) <= 10]
        score = round(((sum(1 for value in values if value >= 9) - sum(1 for value in values if value <= 6)) / len(values) * 100 + 100) / 2, 2) if values else None
    elif row.objective in {"willingness_to_pay", "pricing_validation"}:
        values = [float(value) for value in values if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit())]
        score = round(min(100, len([value for value in values if value > 0]) / len(values) * 100), 2) if values else None
    if score is None: return
    previous = db.query(CustomerValidationBssSnapshot).filter(CustomerValidationBssSnapshot.project_id == row.project_id, CustomerValidationBssSnapshot.evidence_type == row.objective).order_by(CustomerValidationBssSnapshot.created_at.desc()).first()
    db.add(CustomerValidationBssSnapshot(id=uuid.uuid4(), session_id=row.id, project_id=row.project_id, evidence_type=row.objective, previous_score=previous.new_score if previous else None, new_score=score, delta=score - previous.new_score if previous else None, confidence=row.confidence_level, response_count=len(responses), synthesis_hash=_hash(synthesis.findings), calculation_version="customer-validation-bss-v1"))
    db.add(EventLog(event_type="gsis_recompute_requested", event_data={"source": "CUSTOMER_EVIDENCE", "session_id": str(row.id), "evidence_type": row.objective, "bss_score": score}, user_id=row.owner_id, project_id=row.project_id))


class CustomerValidationError(ValueError):
    pass


class CustomerValidationService:
    """Database-backed, append-only customer validation contract."""

    @staticmethod
    def _owned(db: Any, owner_id: str, session_id: str) -> CustomerValidationSession:
        try:
            sid = uuid.UUID(str(session_id)); oid = uuid.UUID(str(owner_id))
        except (ValueError, TypeError):
            raise CustomerValidationError("validation_session_not_found")
        row = db.query(CustomerValidationSession).filter(
            CustomerValidationSession.id == sid,
            CustomerValidationSession.owner_id == oid,
        ).first()
        if row is None:
            raise CustomerValidationError("validation_session_not_found")
        CustomerValidationService._expire_if_needed(db, row)
        return row

    @staticmethod
    def _expire_if_needed(db: Any, row: CustomerValidationSession) -> None:
        if row.status == "active" and row.expires_at and row.expires_at <= _now():
            row.status = "expired"
            CustomerValidationService._event(db, row, "session_expired", {})
            db.commit()

    @staticmethod
    def _event(db: Any, row: CustomerValidationSession, event_type: str, metadata: Dict[str, Any]) -> None:
        previous = db.query(CustomerValidationEvent).filter(
            CustomerValidationEvent.session_id == row.id
        ).order_by(CustomerValidationEvent.created_at.desc()).first()
        payload = {"type": event_type, "session": str(row.id), "metadata": metadata, "at": _now().isoformat()}
        db.add(CustomerValidationEvent(
            id=uuid.uuid4(), session_id=row.id, project_id=row.project_id,
            event_type=event_type, metadata_json=metadata,
            previous_hash=previous.event_hash if previous else None,
            event_hash=_hash({"previous": previous.event_hash if previous else None, **payload}),
        ))

    @staticmethod
    def _validate_questions(questions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen = set()
        for index, item in enumerate(list(questions)[:20]):
            if not isinstance(item, dict):
                raise CustomerValidationError("invalid_question")
            qid = str(item.get("id") or f"q_{index + 1}").strip()
            text = str(item.get("question") or "").strip()
            if not text or qid in seen or len(text) > 500:
                raise CustomerValidationError("invalid_question")
            seen.add(qid)
            answer_type = str(item.get("answer_type") or "long_text")
            options = [str(option).strip()[:200] for option in list(item.get("options") or [])[:50] if str(option).strip()]
            if answer_type not in QUESTION_TYPES or answer_type in {"multiple_choice", "multiple_select", "ranking"} and len(options) < 2:
                raise CustomerValidationError("invalid_question_type")
            normalized.append({
                "id": qid, "question": text,
                "answer_type": answer_type,
                "required": bool(item.get("required", True)),
                "options": options,
            })
        if not normalized:
            raise CustomerValidationError("questions_required")
        return normalized

    @staticmethod
    def create(db: Any, owner_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            oid = uuid.UUID(str(owner_id)); pid = uuid.UUID(str(body.get("project_id") or body.get("projectId")))
        except (ValueError, TypeError):
            raise CustomerValidationError("project_id_required")
        project = db.query(Project).filter(Project.id == pid, Project.owner_id == oid).first()
        if project is None:
            raise CustomerValidationError("project_not_found")
        objective = str(body.get("objective") or "problem_discovery").strip().lower()
        mode = str(body.get("mode") or "survey").strip().lower()
        if objective not in OBJECTIVES or mode not in MODES:
            raise CustomerValidationError("invalid_objective_or_mode")
        project_stage = _stage(project, body.get("stage"))
        questions = CustomerValidationService._validate_questions(body.get("questions") or stage_questions(project_stage, objective, mode))
        now = _now()
        expires = now + timedelta(days=min(max(int(body.get("expiry_days") or 30), 1), 90))
        row = CustomerValidationSession(
            id=uuid.uuid4(), owner_id=oid, project_id=pid,
            incubation_session_id=uuid.UUID(str(body["incubation_session_id"])) if body.get("incubation_session_id") else None,
            hypothesis_id=uuid.UUID(str(body["hypothesis_id"] or body["hypothesisId"])) if body.get("hypothesis_id") or body.get("hypothesisId") else None,
            title=str(body.get("title") or "Customer Validation").strip()[:255],
            description=str(body.get("description") or "").strip()[:2000], objective=objective, mode=mode,
            stage=project_stage, questions=questions,
            respondent_profile=dict(body.get("respondent_profile") or {}),
            source_configuration=dict(body.get("source_configuration") or {}),
            target_respondents=min(max(int(body.get("target_respondents") or 10), 1), 10000),
            status="draft", public_token_hash="pending",
            configuration_hash=_hash({"objective": objective, "mode": mode, "stage": project_stage, "questions": questions}),
            expires_at=expires,
        )
        db.add(row); db.flush(); row.public_token_hash = _hash(_token_for(row.id)); CustomerValidationService._event(db, row, "session_created", {"objective": objective, "mode": mode}); db.commit()
        return _session_dict(row, include_token=True)

    @staticmethod
    def list(db: Any, owner_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        oid = uuid.UUID(str(owner_id))
        rows = db.query(CustomerValidationSession).filter(CustomerValidationSession.owner_id == oid).order_by(CustomerValidationSession.created_at.desc()).limit(min(max(limit, 1), 100)).all()
        for row in rows: CustomerValidationService._expire_if_needed(db, row)
        return [_session_dict(row, include_token=True) for row in rows]

    @staticmethod
    def get(db: Any, owner_id: str, session_id: str) -> Dict[str, Any]:
        return _session_dict(CustomerValidationService._owned(db, owner_id, session_id), include_token=True)

    @staticmethod
    def responses(db: Any, owner_id: str, session_id: str, limit: int = 100) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        items = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id).order_by(CustomerValidationResponse.received_at.desc()).limit(min(max(limit, 1), 500)).all()
        return {"responses": [_response_dict(item) for item in items]}

    @staticmethod
    def events(db: Any, owner_id: str, session_id: str, limit: int = 100) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        items = db.query(CustomerValidationEvent).filter(CustomerValidationEvent.session_id == row.id).order_by(CustomerValidationEvent.created_at.desc()).limit(min(max(limit, 1), 500)).all()
        return {"events": [_event_dict(item) for item in items]}

    @staticmethod
    def insights(db: Any, owner_id: str, session_id: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        if row.qualified_response_count < 3:
            finding = "Evidence accumulating — insufficient sample for synthesis."
        elif row.qualified_response_count < 5:
            finding = "Early signal — treat emerging patterns as provisional."
        elif row.qualified_response_count < 10:
            finding = "Emerging pattern — confidence is still limited."
        else:
            finding = "Repeated customer signal — review synthesis before making a decision."
        return {"sessionId": str(row.id), "responseProgress": {"total": row.total_response_count, "qualified": row.qualified_response_count}, "confidence": row.confidence_level, "evidenceStatement": finding, "synthesisStatus": row.synthesis_status}

    @staticmethod
    def findings(db: Any, owner_id: str, session_id: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        responses = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id, CustomerValidationResponse.evidence_status == "qualified").all()
        findings = _theme_findings(responses)
        findings["whatWeLearned"] = [f"{item['theme'].replace('_', ' ').title()} appeared in {item['count']} qualified responses." for item in findings["recurringPainPoints"]]
        findings["whatRemainsUncertain"] = ["Evidence accumulating — insufficient sample for synthesis."] if len(responses) < 3 else ["Segment differences and causality require additional evidence."]
        return findings

    @staticmethod
    def create_synthesis(db: Any, owner_id: str, session_id: str, *, generated_by: str = "deterministic") -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        responses = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id, CustomerValidationResponse.evidence_status == "qualified").order_by(CustomerValidationResponse.received_at.asc()).all()
        findings = CustomerValidationService.findings(db, owner_id, session_id)
        input_hash = _hash([response.response_hash for response in responses] + [row.configuration_hash])
        existing = db.query(CustomerValidationSynthesis).filter(CustomerValidationSynthesis.session_id == row.id, CustomerValidationSynthesis.input_hash == input_hash).first()
        if existing: return {"synthesis": existing, "cached": True}
        verdict = "Insufficient Evidence" if len(responses) < 3 else "Mixed Signal" if len(findings.get("recurringPainPoints", [])) == 0 else "Partially Validated"
        limitations = ["Founder-generated sample; not statistically significant."]
        version = int(db.query(func.max(CustomerValidationSynthesis.version)).filter(CustomerValidationSynthesis.session_id == row.id).scalar() or 0) + 1
        synthesis = CustomerValidationSynthesis(id=uuid.uuid4(), session_id=row.id, project_id=row.project_id, version=version, input_hash=input_hash, findings=findings, verdict=verdict, confidence=row.confidence_level, limitations=limitations, generated_by=generated_by)
        db.add(synthesis); row.latest_synthesis_id = synthesis.id; row.synthesis_status = "ready"; CustomerValidationService._event(db, row, "synthesis_completed", {"version": version, "verdict": verdict}); _project_event(db, row, "synthesis_completed", {"version": version, "verdict": verdict}); _project_workspace_context(db, row); db.flush(); _bss_snapshot(db, row, synthesis); db.commit()
        if row.hypothesis_id:
            hypothesis = db.query(CustomerValidationHypothesis).filter(CustomerValidationHypothesis.id == row.hypothesis_id).first()
            if hypothesis:
                hypothesis.status = "supported" if verdict == "Validated" else "not_supported" if verdict == "Not Validated" else "testing"
                hypothesis.evidence_summary = {"sessionId": str(row.id), "qualifiedResponses": row.qualified_response_count, "verdict": verdict, "confidence": row.confidence_level}
                db.commit()
        return {"synthesis": synthesis, "cached": False}

    @staticmethod
    def store_ai_synthesis(db: Any, owner_id: str, session_id: str, ai_findings: Dict[str, Any]) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        responses = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id, CustomerValidationResponse.evidence_status == "qualified").order_by(CustomerValidationResponse.received_at.asc()).all()
        input_hash = _hash([response.response_hash for response in responses] + [row.configuration_hash])
        existing = db.query(CustomerValidationSynthesis).filter(CustomerValidationSynthesis.session_id == row.id, CustomerValidationSynthesis.input_hash == input_hash).first()
        if existing and existing.generated_by == "ai_router": return {"synthesis": existing, "cached": True}
        deterministic = CustomerValidationService.findings(db, owner_id, session_id)
        merged = {**deterministic, **{key: value for key, value in ai_findings.items() if key in {"what_we_learned", "what_customers_currently_do", "what_customers_want", "recurring_pain_points", "objections", "contradictions", "surprises", "evidence_gaps", "limitations"}}}
        verdict = "Insufficient Evidence" if len(responses) < 3 else "Mixed Signal" if merged.get("contradictions") and len(responses) < 10 else "Partially Validated"
        version = int(db.query(func.max(CustomerValidationSynthesis.version)).filter(CustomerValidationSynthesis.session_id == row.id).scalar() or 0) + 1
        synthesis = CustomerValidationSynthesis(id=uuid.uuid4(), session_id=row.id, project_id=row.project_id, version=version, input_hash=input_hash, findings=merged, verdict=verdict, confidence=row.confidence_level, limitations=list(merged.get("limitations") or ["Founder-generated sample; not statistically significant."]), generated_by="ai_router")
        db.add(synthesis); row.latest_synthesis_id = synthesis.id; row.synthesis_status = "ready"; CustomerValidationService._event(db, row, "synthesis_completed", {"version": version, "verdict": verdict, "generated_by": "ai_router"}); _project_event(db, row, "synthesis_completed", {"version": version, "verdict": verdict}); _project_workspace_context(db, row); db.flush(); _bss_snapshot(db, row, synthesis); db.commit()
        return {"synthesis": synthesis, "cached": False}

    @staticmethod
    def recommendations(db: Any, owner_id: str, session_id: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        findings = CustomerValidationService.findings(db, owner_id, session_id)
        theme_names = {item["theme"] for item in findings.get("recurringPainPoints", [])}
        recs: List[Dict[str, Any]] = []
        if row.qualified_response_count < 10:
            recs.append({"title": "Collect more qualified responses", "reason": "The current sample is below the stronger evidence threshold.", "key": "collect_qualified_responses", "urgency": "HIGH"})
        if row.objective in {"willingness_to_pay", "pricing_validation"} or "cost" not in theme_names:
            recs.append({"title": "Validate willingness to pay", "reason": "Current customer evidence does not establish current spending behaviour.", "key": "validate_willingness_to_pay", "urgency": "HIGH"})
        result = []
        for item in recs:
            key = item.pop("key")
            existing = db.query(CustomerValidationRecommendation).filter(CustomerValidationRecommendation.session_id == row.id, CustomerValidationRecommendation.deduplication_key == key).first()
            if existing is None:
                existing = CustomerValidationRecommendation(id=uuid.uuid4(), session_id=row.id, project_id=row.project_id, deduplication_key=key, title=item["title"], reason=item["reason"], evidence={"qualifiedResponses": row.qualified_response_count}, urgency=item["urgency"], expected_impact="HIGH", estimated_effort="MEDIUM", confidence=row.confidence_level, source_engines=["Customer Validation"], status="recommended")
                db.add(existing)
            result.append(existing)
        db.commit()
        return {"recommendations": [{"id": str(item.id), "title": item.title, "reason": item.reason, "urgency": item.urgency, "confidence": item.confidence, "sourceEngines": item.source_engines, "status": item.status} for item in result]}

    @staticmethod
    def aggregate_recommendations(db: Any, owner_id: str, session_id: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        customer = CustomerValidationService.recommendations(db, owner_id, session_id)["recommendations"]
        from database_schema import GsisV2Recommendation
        existing = db.query(GsisV2Recommendation).filter(GsisV2Recommendation.project_id == row.project_id, GsisV2Recommendation.status == "recommended").order_by(GsisV2Recommendation.created_at.desc()).limit(20).all()
        merged: Dict[str, Dict[str, Any]] = {}
        for item in customer:
            key = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
            merged[key] = {**item, "sourceEngines": list(dict.fromkeys(item.get("sourceEngines", []) + ["Customer Validation"]))}
        for item in existing:
            key = re.sub(r"[^a-z0-9]+", " ", item.action.lower()).strip()
            match = next((candidate for candidate in merged if key in candidate or candidate in key), None)
            if match:
                merged[match]["sourceEngines"] = list(dict.fromkeys(merged[match]["sourceEngines"] + ["GSIS"]))
            else:
                merged[key] = {"id": str(item.id), "title": item.action, "reason": "Existing GSIS recommendation.", "urgency": item.expected_impact or "MEDIUM", "confidence": str(item.confidence or "unknown"), "sourceEngines": ["GSIS"], "status": item.status}
        return {"recommendations": sorted(merged.values(), key=lambda item: (item.get("urgency") != "HIGH", item["title"]))}

    @staticmethod
    def update_recommendation(db: Any, owner_id: str, session_id: str, recommendation_id: str, status: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        if status not in {"accepted", "in_progress", "completed", "dismissed"}: raise CustomerValidationError("invalid_recommendation_status")
        try: rid = uuid.UUID(str(recommendation_id))
        except ValueError: raise CustomerValidationError("recommendation_not_found")
        recommendation = db.query(CustomerValidationRecommendation).filter(CustomerValidationRecommendation.id == rid, CustomerValidationRecommendation.session_id == row.id).first()
        if recommendation is None: raise CustomerValidationError("recommendation_not_found")
        recommendation.status = status; recommendation.updated_at = _now(); CustomerValidationService._event(db, row, "recommendation_updated", {"recommendation_id": str(rid), "status": status}); db.commit()
        return {"id": str(recommendation.id), "status": recommendation.status}

    @staticmethod
    def create_share(db: Any, owner_id: str, session_id: str, scope: str = "private") -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        if scope not in {"private", "team", "mentor", "accelerator", "investor", "public"}: raise CustomerValidationError("invalid_share_scope")
        findings = CustomerValidationService.findings(db, owner_id, session_id)
        if scope == "public":
            findings = {**findings, "recurringPainPoints": [{key: value for key, value in item.items() if key != "quotes"} for item in findings.get("recurringPainPoints", [])]}
        report = {"title": row.title, "objective": row.objective, "stage": row.stage, "totalResponses": row.total_response_count, "qualifiedResponses": row.qualified_response_count, "confidence": row.confidence_level, "findings": findings, "methodology": "Immutable TechIT-recorded customer evidence; raw responses excluded."}
        token = secrets.token_urlsafe(32); share = CustomerValidationShare(id=uuid.uuid4(), session_id=row.id, project_id=row.project_id, owner_id=row.owner_id, scope=scope, share_token_hash=_hash(token), report_hash=_hash(report), report=report)
        db.add(share); CustomerValidationService._event(db, row, "share_created", {"scope": scope}); db.commit()
        return {"shareToken": token, "report": report}

    @staticmethod
    def investor_evidence(db: Any, owner_id: str, project_id: str) -> Dict[str, Any]:
        oid, pid = uuid.UUID(str(owner_id)), uuid.UUID(str(project_id))
        project = db.query(Project).filter(Project.id == pid, Project.owner_id == oid).first()
        if not project: raise CustomerValidationError("project_not_found")
        sessions = db.query(CustomerValidationSession).filter(CustomerValidationSession.project_id == pid).all()
        latest = db.query(CustomerValidationSynthesis).filter(CustomerValidationSynthesis.project_id == pid).order_by(CustomerValidationSynthesis.created_at.desc()).first()
        return {"projectId": project_id, "validationRounds": len(sessions), "totalResponses": sum(row.total_response_count for row in sessions), "qualifiedResponses": sum(row.qualified_response_count for row in sessions), "objectives": sorted({row.objective for row in sessions}), "latestVerdict": latest.verdict if latest else "Insufficient Evidence", "confidence": latest.confidence if latest else "insufficient", "lastUpdated": max((row.updated_at for row in sessions), default=None).isoformat() if sessions else None, "rawResponsesShared": False, "source": "TechIT Customer Evidence"}

    @staticmethod
    def transition(db: Any, owner_id: str, session_id: str, action: str) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        if action == "activate":
            if row.status not in {"draft", "paused"}: raise CustomerValidationError("session_not_resumable")
            row.status = "active"; row.activated_at = _now(); CustomerValidationService._event(db, row, "session_activated", {})
        elif action == "pause":
            if row.status != "active": raise CustomerValidationError("session_not_active")
            row.status = "paused"; CustomerValidationService._event(db, row, "session_paused", {})
        elif action == "complete":
            if row.status not in {"active", "paused"}: raise CustomerValidationError("session_not_completable")
            row.status = "completed"; row.completed_at = _now(); CustomerValidationService._event(db, row, "session_completed", {})
        else: raise CustomerValidationError("invalid_session_action")
        db.commit(); return _session_dict(row, include_token=True)

    @staticmethod
    def update_draft(db: Any, owner_id: str, session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        row = CustomerValidationService._owned(db, owner_id, session_id)
        if row.status != "draft" or row.configuration_locked:
            raise CustomerValidationError("configuration_locked")
        if "questions" in body: row.questions = CustomerValidationService._validate_questions(body["questions"])
        if "title" in body: row.title = str(body["title"] or row.title).strip()[:255]
        if "description" in body: row.description = str(body["description"] or "").strip()[:2000]
        row.configuration_hash = _hash({"objective": row.objective, "mode": row.mode, "stage": row.stage, "questions": row.questions or []})
        db.commit(); return _session_dict(row, include_token=True)

    @staticmethod
    def public_get(db: Any, token: str) -> Dict[str, Any]:
        row = db.query(CustomerValidationSession).filter(CustomerValidationSession.public_token_hash == _hash(token)).first()
        if row is None: raise CustomerValidationError("validation_not_found")
        CustomerValidationService._expire_if_needed(db, row)
        if row.status not in ACTIVE_STATES: raise CustomerValidationError("validation_not_active")
        return _public_session(row)

    @staticmethod
    def submit(db: Any, token: str, answers: Dict[str, Any], source: str = "direct", anonymous_id: Optional[str] = None) -> Dict[str, Any]:
        row = db.query(CustomerValidationSession).filter(CustomerValidationSession.public_token_hash == _hash(token)).first()
        if row is None: raise CustomerValidationError("validation_not_found")
        CustomerValidationService._expire_if_needed(db, row)
        if row.status not in ACTIVE_STATES: raise CustomerValidationError("validation_not_accepting_responses")
        rate_key = f"{row.id}:{_hash(anonymous_id or 'anonymous')}"; window = _RATE_WINDOWS[rate_key]; cutoff = _now() - timedelta(minutes=10)
        while window and window[0] < cutoff: window.popleft()
        if len(window) >= 5: raise CustomerValidationError("rate_limit_exceeded")
        window.append(_now())
        questions = row.questions or []; clean: Dict[str, Any] = {}
        for question in questions:
            qid = question["id"]; value = answers.get(qid)
            if question.get("required") and (value is None or not str(value).strip()):
                raise CustomerValidationError("required_answer_missing")
            if value is not None:
                answer_type = question.get("answer_type", "long_text"); options = question.get("options") or []
                if answer_type in {"multiple_select", "ranking"}:
                    if not isinstance(value, list) or any(str(item) not in options for item in value): raise CustomerValidationError("invalid_answer_schema")
                    value = value[:50]
                elif answer_type == "multiple_choice" and str(value) not in options: raise CustomerValidationError("invalid_answer_schema")
                elif answer_type == "yes_no" and value not in {True, False, "yes", "no"}: raise CustomerValidationError("invalid_answer_schema")
                elif answer_type in {"rating", "likert"} and not str(value).isdigit(): raise CustomerValidationError("invalid_answer_schema")
                elif answer_type == "nps" and (not str(value).isdigit() or not 0 <= int(value) <= 10): raise CustomerValidationError("invalid_answer_schema")
                elif answer_type in {"numeric", "willingness_to_pay"}:
                    try: float(value)
                    except (TypeError, ValueError): raise CustomerValidationError("invalid_answer_schema")
                elif len(str(value)) > 5000: raise CustomerValidationError("answer_too_long")
                clean[qid] = value
        answer_hash = _hash(clean)
        duplicate = db.query(CustomerValidationResponse).filter(CustomerValidationResponse.session_id == row.id, CustomerValidationResponse.answer_hash == answer_hash).first()
        if duplicate: raise CustomerValidationError("duplicate_response")
        answered = sum(1 for question in questions if clean.get(question["id"]) not in (None, "", []))
        completion = answered / len(questions) if questions else 0
        meaningful = sum(1 for value in clean.values() if len(str(value).strip()) >= 8)
        reasons = []
        if meaningful == 0: reasons.append("answers_not_meaningful")
        if completion < 1: reasons.append("incomplete")
        quality = "INVALID" if completion < 1 else "LOW" if meaningful < max(1, len(questions) // 3) else "MEDIUM" if meaningful < len(questions) else "HIGH"
        evidence_status = "qualified" if quality in {"HIGH", "MEDIUM"} else "excluded" if quality == "INVALID" else "weak"
        received = _now(); response = CustomerValidationResponse(
            id=uuid.uuid4(), session_id=row.id, answers=clean, answer_hash=answer_hash,
            response_hash=_hash({"session": str(row.id), "answers": clean, "received": received.isoformat()}),
            anonymous_browser_hash=_hash(anonymous_id) if anonymous_id else None, source=source[:40],
            quality_classification=quality, evidence_status=evidence_status, quality_reasons=reasons,
            completion_percentage=completion, classified_at=received,
        )
        db.add(response); row.total_response_count += 1
        counts = dict(row.quality_counts or {}); counts[quality.lower()] = int(counts.get(quality.lower(), 0)) + 1; row.quality_counts = counts
        if evidence_status == "qualified": row.qualified_response_count += 1
        row.configuration_locked = True
        row.confidence_level = "insufficient" if row.qualified_response_count < 3 else "low" if row.qualified_response_count < 5 else "medium" if row.qualified_response_count < 10 else "high"
        CustomerValidationService._event(db, row, "response_received", {"response_count": row.total_response_count, "qualified_count": row.qualified_response_count})
        CustomerValidationService._event(db, row, "response_classified", {"quality": quality, "evidence_status": evidence_status})
        if row.qualified_response_count in {3, 5, 10, 25, 50}:
            CustomerValidationService._event(db, row, "threshold_reached", {"qualified_count": row.qualified_response_count})
            _project_event(db, row, "threshold_reached", {"qualified_count": row.qualified_response_count})
        _project_workspace_context(db, row)
        db.commit()
        if row.qualified_response_count >= 3 and row.qualified_response_count in {3, 5, 10, 25, 50}:
            try:
                from workers.workers import validation_synthesis_generate, validation_recommendation_update
                validation_synthesis_generate.delay(str(row.id), str(row.owner_id))
                validation_recommendation_update.delay(str(row.id), str(row.owner_id))
            except Exception:
                pass
        return {"message": "Thank you. Your response has been recorded."}

    @staticmethod
    def history(db: Any, owner_id: str, project_id: str) -> Dict[str, Any]:
        oid, pid = uuid.UUID(str(owner_id)), uuid.UUID(str(project_id))
        rows = db.query(CustomerValidationSession).filter(CustomerValidationSession.owner_id == oid, CustomerValidationSession.project_id == pid).order_by(CustomerValidationSession.created_at.asc()).all()
        timeline = [{"id": str(row.id), "title": row.title, "objective": row.objective, "qualifiedResponses": row.qualified_response_count, "confidence": row.confidence_level, "status": row.status, "createdAt": row.created_at.isoformat()} for row in rows]
        changes = []
        for previous, current in zip(rows, rows[1:]):
            changes.append({"from": str(previous.id), "to": str(current.id), "qualifiedDelta": current.qualified_response_count - previous.qualified_response_count, "confidenceChanged": previous.confidence_level != current.confidence_level})
        return {"timeline": timeline, "changes": changes}

    @staticmethod
    def create_hypothesis(db: Any, owner_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        oid, pid = uuid.UUID(str(owner_id)), uuid.UUID(str(body.get("project_id") or body.get("projectId")))
        project = db.query(Project).filter(Project.id == pid, Project.owner_id == oid).first()
        if not project: raise CustomerValidationError("project_not_found")
        statement = str(body.get("statement") or "").strip()
        if len(statement) < 10: raise CustomerValidationError("hypothesis_statement_required")
        row = CustomerValidationHypothesis(id=uuid.uuid4(), project_id=pid, owner_id=oid, statement=statement, status="untested", evidence_summary={})
        db.add(row); db.commit(); return {"id": str(row.id), "statement": row.statement, "status": row.status}
