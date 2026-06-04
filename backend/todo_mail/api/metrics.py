from fastapi import APIRouter

from ..db import get_conn

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    with get_conn() as conn:
        # Median reply latency in hours (replied tasks only)
        latencies = conn.execute(
            """SELECT (julianday(t.updated_at) - julianday(m.received_at)) * 24.0 AS hours
               FROM tasks t
               JOIN messages m ON t.message_id = m.id
               WHERE t.status = 'replied'
               ORDER BY hours"""
        ).fetchall()
        median_latency = _median([r[0] for r in latencies if r[0] is not None])

        # Open tasks that are past their reply_by (missed replies)
        missed = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'open' AND reply_by < datetime('now')"
        ).fetchone()[0]

        # Trust index: "not a task" feedbacks per 100 LLM classifications
        llm_classifications = conn.execute(
            "SELECT COUNT(*) FROM classifications WHERE model != 'pre-filter'"
        ).fetchone()[0]
        not_a_task_count = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE kind = 'not_a_task'"
        ).fetchone()[0]
        trust_index = (
            round((not_a_task_count / llm_classifications) * 100, 1)
            if llm_classifications > 0 else None
        )

        # Activation funnel counts
        funnel_rows = conn.execute(
            "SELECT kind, COUNT(*) as n FROM events GROUP BY kind"
        ).fetchall()
        funnel = {r["kind"]: r["n"] for r in funnel_rows}

        # Task counts by status
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as n FROM tasks GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["n"] for r in status_rows}

    return {
        "median_reply_latency_hours": median_latency,
        "open_overdue_count": missed,
        "trust_index_dismissals_per_100": trust_index,
        "llm_classifications_total": llm_classifications,
        "tasks_by_status": by_status,
        "funnel": funnel,
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
