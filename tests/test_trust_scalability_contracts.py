from database_schema import (
    InvestorTrustNote,
    InvestorWatchlist,
    TrustProfile,
    TrustVerificationHistory,
)


def _index_columns(model: object) -> dict[str, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in model.__table__.indexes
    }


def test_investor_trust_lookup_indexes_cover_dashboard_paths() -> None:
    watchlist_indexes = _index_columns(InvestorWatchlist)
    notes_indexes = _index_columns(InvestorTrustNote)

    assert watchlist_indexes["idx_watchlist_investor_project"] == ("investor_id", "project_id")
    assert notes_indexes["idx_investor_trust_notes_investor_updated"] == ("investor_id", "updated_at")


def test_trust_profile_indexes_cover_status_and_score_dashboards() -> None:
    indexes = _index_columns(TrustProfile)

    assert indexes["idx_trust_profile_project_status"] == ("project_id", "verification_status")
    assert indexes["idx_trust_profile_status_score"] == ("verification_status", "trust_score")


def test_trust_history_indexes_cover_project_timeline_and_expiry_scans() -> None:
    indexes = _index_columns(TrustVerificationHistory)

    assert indexes["idx_trust_history_project_created"] == ("project_id", "created_at")
    assert indexes["idx_trust_history_source_expiry"] == ("source", "expires_at")
