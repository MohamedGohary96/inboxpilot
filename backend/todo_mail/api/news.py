from fastapi import APIRouter, HTTPException, Query

from ..db import get_conn

router = APIRouter()

_VALID_CATEGORIES = {"release", "security", "discussion", "newsletter", "pull_request", "issue"}


_BASE_WHERE = (
    "WHERE m.news_category IS NOT NULL"
    " AND COALESCE(m.news_dismissed, 0) = 0"
)


@router.get("/news")
def list_news(
    category: str | None = Query(default=None),
    repo: str | None = Query(default=None),
    limit: int = 200,
):
    sql = f"""
        SELECT m.id, m.sender, m.sender_email, m.subject, m.received_at,
               m.news_category, m.news_repo, m.news_summary, m.snippet,
               m.thread_id, m.gmail_message_id,
               (t.id IS NOT NULL) AS is_task,
               t.id AS task_id
        FROM messages m
        LEFT JOIN tasks t ON t.message_id = m.id
        {_BASE_WHERE}
    """
    params: list = []
    if category:
        if category not in _VALID_CATEGORIES:
            raise HTTPException(400, "invalid category")
        sql += " AND m.news_category = ?"
        params.append(category)
    if repo:
        sql += " AND m.news_repo = ?"
        params.append(repo)
    sql += " ORDER BY m.received_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/news/unread-count")
def unread_count():
    sql = f"SELECT COUNT(*) AS c FROM messages m {_BASE_WHERE}"
    with get_conn() as conn:
        row = conn.execute(sql).fetchone()
    return {"count": row["c"]}


@router.post("/news/{message_id}/summarize")
def summarize(message_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM messages WHERE id = ? AND news_category IS NOT NULL",
            (message_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "news item not found")

    from ..classify import summarize_news
    summary = summarize_news(message_id)
    if not summary:
        raise HTTPException(503, "Could not generate summary")
    return {"summary": summary}


@router.post("/news/{message_id}/dismiss")
def dismiss(message_id: int):
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE messages SET news_dismissed = 1 WHERE id = ? AND news_category IS NOT NULL",
            (message_id,),
        )
        if result.rowcount == 0:
            raise HTTPException(404, "news item not found")
    return {"ok": True}


@router.post("/news/dismiss-all")
def dismiss_all(category: str | None = None, repo: str | None = None):
    sql = "UPDATE messages SET news_dismissed = 1 WHERE news_category IS NOT NULL AND COALESCE(news_dismissed, 0) = 0"
    params: list = []
    if category:
        if category not in _VALID_CATEGORIES:
            raise HTTPException(400, "invalid category")
        sql += " AND news_category = ?"
        params.append(category)
    if repo:
        sql += " AND news_repo = ?"
        params.append(repo)
    with get_conn() as conn:
        result = conn.execute(sql, params)
    return {"ok": True, "dismissed": result.rowcount}
