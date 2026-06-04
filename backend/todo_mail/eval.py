import json
from datetime import datetime
from pathlib import Path

_BASE = Path.home() / ".local" / "share" / "todo-mail" / "eval"
GOLD_FILE = _BASE / "gold.jsonl"
RUNS_DIR = _BASE / "runs"


# ── gold set helpers ──────────────────────────────────────────────────────────

def load_gold() -> list[dict]:
    if not GOLD_FILE.exists():
        return []
    return [json.loads(l) for l in GOLD_FILE.read_text().splitlines() if l.strip()]


def _append_gold(entry: dict) -> None:
    _BASE.mkdir(parents=True, exist_ok=True)
    with GOLD_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── label command ─────────────────────────────────────────────────────────────

def run_label(n: int) -> None:
    """Interactive session: show each email, record human label."""
    from .db import get_conn

    labeled_ids = {e["message_id"] for e in load_gold()}

    if labeled_ids:
        placeholders = ",".join("?" * len(labeled_ids))
        sql = f"""
            SELECT m.*,
                (SELECT raw_json FROM classifications
                 WHERE message_id = m.id ORDER BY id DESC LIMIT 1) AS claude_json
            FROM messages m
            WHERE m.id NOT IN ({placeholders})
            ORDER BY m.received_at DESC LIMIT ?
        """
        params: tuple = (*labeled_ids, n)
    else:
        sql = """
            SELECT m.*,
                (SELECT raw_json FROM classifications
                 WHERE message_id = m.id ORDER BY id DESC LIMIT 1) AS claude_json
            FROM messages m
            ORDER BY m.received_at DESC LIMIT ?
        """
        params = (n,)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        print("No unlabeled messages found. Run 'todo-mail start' and poll some emails first.")
        return

    print(f"\nLabeling {len(rows)} email(s).  y=task  n=not-a-task  s=skip  q=quit\n")

    saved = 0
    for i, row in enumerate(rows, 1):
        msg = dict(row)
        claude: dict = {}
        if msg.get("claude_json"):
            try:
                claude = json.loads(msg["claude_json"])
            except Exception:
                pass

        print("━" * 60)
        print(f"Email {i} / {len(rows)}")
        print("━" * 60)
        print(f"From:    {msg.get('sender', '')} <{msg.get('sender_email', '')}>")
        print(f"Subject: {msg.get('subject', '')}")
        print(f"Date:    {msg.get('received_at', '')}")
        print()
        body = (msg.get("body_text") or "")[:500]
        print(body or "(no body)")
        if len(msg.get("body_text") or "") > 500:
            print("... (truncated)")
        print()

        if claude:
            if claude.get("is_task"):
                print(
                    f"Claude: TASK — \"{claude.get('task_summary', '')}\"  "
                    f"priority={claude.get('priority', '')}  "
                    f"deadline_confidence={claude.get('deadline_confidence', '')}"
                )
            else:
                print(f"Claude: not a task — {claude.get('reasoning', '')}")
        else:
            print("Claude: not yet classified")
        print()

        answer = input("Is this a task? [Y/n/s/q]: ").strip().lower() or "y"
        if answer == "q":
            print("\nQuitting.")
            break
        if answer == "s":
            print("Skipped.\n")
            continue

        is_task = answer != "n"
        task_summary: str | None = None
        deadline: str | None = None

        if is_task:
            default = claude.get("task_summary", "")
            prompt = f"Task summary [{default}]: " if default else "Task summary: "
            entered = input(prompt).strip()
            task_summary = entered or default or None

            dl = input("Deadline (YYYY-MM-DD or blank): ").strip()
            if dl:
                try:
                    deadline = datetime.strptime(dl, "%Y-%m-%d").isoformat()
                except ValueError:
                    print("Invalid date — skipping deadline.")

        _append_gold({
            "message_id": msg["id"],
            "gmail_message_id": msg["gmail_message_id"],
            "subject": msg.get("subject", ""),
            "sender": msg.get("sender", ""),
            "received_at": msg.get("received_at", ""),
            "is_task": is_task,
            "task_summary": task_summary,
            "deadline": deadline,
            "labeled_at": datetime.utcnow().isoformat(),
        })
        saved += 1
        print("Saved.\n")

    total = len(load_gold())
    print(f"Session done — saved {saved} label(s). Gold set total: {total}")
    print(f"File: {GOLD_FILE}")


# ── eval command ──────────────────────────────────────────────────────────────

def run_eval() -> None:
    """Re-classify every gold entry with Claude and report quality metrics."""
    from .classify import classify_for_eval

    gold = load_gold()
    if not gold:
        print("No gold labels found. Run 'todo-mail label' first.")
        return

    print(f"\nRunning eval on {len(gold)} labeled email(s) — this calls Claude for each one.\n")

    results: list[dict] = []
    for entry in gold:
        print(".", end="", flush=True)
        prediction = classify_for_eval(entry["message_id"])
        results.append({"gold": entry, "prediction": prediction})
    print()

    _report(results)


def _report(results: list[dict]) -> None:
    from rapidfuzz import fuzz

    tp = fp = fn = tn = 0
    summary_exact = summary_fuzzy = summary_total = 0
    deadline_within = deadline_total = 0

    for r in results:
        gold_task: bool = r["gold"]["is_task"]
        pred = r["prediction"]
        pred_task: bool = bool(pred and pred.get("is_task"))

        if gold_task and pred_task:
            tp += 1
        elif not gold_task and pred_task:
            fp += 1
        elif gold_task and not pred_task:
            fn += 1
        else:
            tn += 1

        if gold_task and pred_task and r["gold"].get("task_summary") and pred:
            summary_total += 1
            g = r["gold"]["task_summary"].lower().strip()
            p = (pred.get("task_summary") or "").lower().strip()
            if g == p:
                summary_exact += 1
            if fuzz.ratio(g, p) >= 85:
                summary_fuzzy += 1

        if gold_task and pred_task and r["gold"].get("deadline") and pred:
            pred_dl = pred.get("extracted_deadline")
            if pred_dl:
                deadline_total += 1
                try:
                    from datetime import timedelta
                    g_dt = datetime.fromisoformat(r["gold"]["deadline"])
                    p_dt = datetime.fromisoformat(pred_dl)
                    if abs((g_dt - p_dt).total_seconds()) <= 4 * 3600:
                        deadline_within += 1
                except Exception:
                    pass

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    total = len(results)
    n_tasks = sum(1 for r in results if r["gold"]["is_task"])

    print(f"\n{'='*52}")
    print("Eval Results")
    print(f"{'='*52}")
    print(f"Gold samples: {total}  ({n_tasks} tasks, {total - n_tasks} non-tasks)\n")
    print("is_task:")
    print(f"  Precision : {precision:.2f}  ({tp}/{tp + fp} predicted tasks were correct)")
    print(f"  Recall    : {recall:.2f}  ({tp}/{tp + fn} actual tasks were found)")
    print(f"  F1        : {f1:.2f}")

    if summary_total:
        print(f"\ntask_summary (on {summary_total} true positives):")
        print(f"  Exact match : {summary_exact}/{summary_total} ({100*summary_exact//summary_total}%)")
        print(f"  Fuzzy ≥ 85  : {summary_fuzzy}/{summary_total} ({100*summary_fuzzy//summary_total}%)")

    if deadline_total:
        print(f"\nextracted_deadline (on {deadline_total} gold entries with deadline):")
        print(f"  Within ±4h : {deadline_within}/{deadline_total} ({100*deadline_within//deadline_total}%)")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    run_file = RUNS_DIR / f"{ts}.json"
    run_file.write_text(json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "total": total,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "summary_exact_rate": round(summary_exact / summary_total, 4) if summary_total else None,
        "summary_fuzzy_rate": round(summary_fuzzy / summary_total, 4) if summary_total else None,
        "deadline_within_4h_rate": round(deadline_within / deadline_total, 4) if deadline_total else None,
        "results": results,
    }, indent=2, default=str))
    print(f"\nSaved to: {run_file}")
