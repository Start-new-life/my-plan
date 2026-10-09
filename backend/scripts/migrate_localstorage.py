"""Import a V1 plan_*.json export into SQLite. Does not write weekly_reviews / chat."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_session, init_engine  # noqa: E402

DRIVE_KEY_RE = re.compile(r"^plan_drive_done_(\d{4}-\d{2}-\d{2})$")

TASKS_DEFAULT = [
    {
        "id": "lc",
        "name": "力扣刷题（Java）",
        "description": "每天 1 道，积累 80+ 高频题",
        "priority": 1,
        "progress": 12,
        "target": 80,
    },
    {
        "id": "cet6",
        "name": "英语六级",
        "description": "每天背词 + 周末真题",
        "priority": 1,
        "progress": 3,
        "target": 30,
    },
    {
        "id": "intern",
        "name": "实习准备",
        "description": "项目 / 简历 / 八股文",
        "priority": 1,
        "progress": 20,
        "target": 100,
    },
    {
        "id": "math",
        "name": "数学竞赛",
        "description": "当作数一预科，跟着进度",
        "priority": 2,
        "progress": 15,
        "target": 40,
    },
    {
        "id": "gpa",
        "name": "信息安全专业课",
        "description": "正常上课，保持 GPA",
        "priority": 2,
        "progress": 60,
        "target": 100,
    },
    {
        "id": "408",
        "name": "408 摸底",
        "description": "每周翻 1 章，先混脸熟",
        "priority": 2,
        "progress": 2,
        "target": 30,
    },
    {
        "id": "hobby",
        "name": "吉他 / 剪辑 / 口语",
        "description": "暂缓，碎片时间随缘",
        "priority": 3,
        "progress": 0,
        "target": 100,
    },
]

GOAL_DEFAULTS = {
    "cet": {"name": "六级词汇", "unit": "词", "total": 1443, "done": 0, "deadline": "2026-12-12"},
    "math": {"name": "数学竞赛", "unit": "集", "total": 31, "done": 10, "deadline": "2026-09-24"},
    "lc": {"name": "力扣刷题", "unit": "题", "total": 150, "done": 0, "deadline": "2026-12-01"},
}

UI_KEY_MAP = {
    "plan_sort_state": "sort_state",
    "plan_collapse_state": "collapse_state",
    "plan_history_collapsed": "history_collapsed",
    "plan_quick_links": "quick_links",
    "plan_palette_last": "palette_last",
    "plan_quote_last": "quote_last",
}


def parse_value(raw: Any) -> Any:
    """Export values are localStorage strings; already-parsed objects also work."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    if not isinstance(raw, str):
        return raw
    text_val = raw.strip()
    if not text_val:
        return None
    try:
        return json.loads(text_val)
    except json.JSONDecodeError:
        return raw


def load_export(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("export root must be a JSON object")
    return {str(k): parse_value(v) for k, v in data.items()}


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def ensure_daily_log(session: Session, date: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO daily_logs (date)
            VALUES (:date)
            ON CONFLICT(date) DO NOTHING
            """
        ),
        {"date": date},
    )


def seed_tasks(session: Session) -> None:
    for t in TASKS_DEFAULT:
        session.execute(
            text(
                """
                INSERT INTO tasks (id, name, description, priority, progress, target)
                VALUES (:id, :name, :description, :priority, :progress, :target)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    priority = excluded.priority
                """
            ),
            t,
        )


def apply_progress_data(session: Session, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    progress_map = payload.get("progress") or {}
    if not isinstance(progress_map, dict):
        return
    now = datetime.now().isoformat(timespec="seconds")
    for task_id, stats in progress_map.items():
        if not isinstance(stats, dict):
            continue
        session.execute(
            text(
                """
                UPDATE tasks
                SET progress = :progress,
                    target = :target,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": task_id,
                "progress": int(stats.get("progress") or 0),
                "target": int(stats["target"]) if stats.get("target") is not None else 1,
                "updated_at": now,
            },
        )


def apply_settings(session: Session, settings: Any) -> None:
    if not isinstance(settings, dict):
        settings = {}
    cet = {**GOAL_DEFAULTS["cet"], **(settings.get("cet") or {})}
    math = {**GOAL_DEFAULTS["math"], **(settings.get("math") or {})}
    lc = {**GOAL_DEFAULTS["lc"], **(settings.get("lc") or {})}
    rows = [
        ("cet", cet["name"], int(cet.get("total") or 0), int(cet.get("done") or 0), cet.get("examDate") or cet.get("deadline"), cet["unit"]),
        ("math", math["name"], int(math.get("total") or 0), int(math.get("done") or 0), math.get("deadline"), math["unit"]),
        ("lc", lc["name"], int(lc.get("total") or 0), int(lc.get("done") or 0), lc.get("deadline"), lc["unit"]),
    ]
    for goal_id, name, total, done, deadline, unit in rows:
        session.execute(
            text(
                """
                INSERT INTO goals (id, name, total, done, deadline, unit)
                VALUES (:id, :name, :total, :done, :deadline, :unit)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    total = excluded.total,
                    done = excluded.done,
                    deadline = excluded.deadline,
                    unit = excluded.unit
                """
            ),
            {
                "id": goal_id,
                "name": name,
                "total": total,
                "done": done,
                "deadline": deadline,
                "unit": unit,
            },
        )

    milestones = settings.get("milestones") or {}
    for mid, default_date in (("m1", "2026-10-01"), ("m2", "2026-10-20"), ("m3", "2026-10-31")):
        session.execute(
            text(
                """
                INSERT INTO milestones (id, label, target_date)
                VALUES (:id, :label, :target_date)
                ON CONFLICT(id) DO UPDATE SET target_date = excluded.target_date
                """
            ),
            {
                "id": mid,
                "label": f"里程碑 {mid}",
                "target_date": milestones.get(mid) or default_date,
            },
        )


def apply_history(session: Session, history: Any) -> None:
    if not isinstance(history, list):
        return
    for row in history:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        date = row["date"]
        ensure_daily_log(session, date)
        session.execute(
            text(
                """
                UPDATE daily_logs
                SET tasks_done = :done,
                    tasks_total = :total,
                    completion_pct = :pct,
                    updated_at = datetime('now')
                WHERE date = :date
                """
            ),
            {
                "date": date,
                "done": row.get("done"),
                "total": row.get("total"),
                "pct": row.get("pct"),
            },
        )


def apply_today_done(session: Session, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    date = payload.get("date")
    ids = payload.get("list") or []
    if not date or not isinstance(ids, list):
        return
    ensure_daily_log(session, date)
    for task_id in ids:
        session.execute(
            text(
                """
                INSERT INTO daily_task_checks (date, task_id)
                VALUES (:date, :task_id)
                ON CONFLICT(date, task_id) DO NOTHING
                """
            ),
            {"date": date, "task_id": task_id},
        )


def apply_three_tasks(session: Session, payload: Any) -> None:
    if not isinstance(payload, dict) or not payload.get("date"):
        return
    date = payload["date"]
    items = payload.get("items") or ["", "", ""]
    done = payload.get("done") or [False, False, False]
    ensure_daily_log(session, date)
    session.execute(
        text(
            """
            UPDATE daily_logs
            SET three_items_json = :items,
                three_done_json = :done,
                updated_at = datetime('now')
            WHERE date = :date
            """
        ),
        {"date": date, "items": dumps(items), "done": dumps(done)},
    )


def apply_week_manual(session: Session, payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    for date, plan_text in payload.items():
        if not date or plan_text is None:
            continue
        ensure_daily_log(session, str(date))
        session.execute(
            text(
                """
                UPDATE daily_logs
                SET week_plan_text = :text,
                    updated_at = datetime('now')
                WHERE date = :date
                """
            ),
            {"date": str(date), "text": str(plan_text)},
        )


def apply_drive_logs(session: Session, export: dict[str, Any]) -> None:
    for key, payload in export.items():
        match = DRIVE_KEY_RE.match(key)
        if not match or not isinstance(payload, dict):
            continue
        date = match.group(1)
        ensure_daily_log(session, date)
        for goal_id in ("cet", "math", "lc"):
            count = payload.get(goal_id)
            if not count:
                continue
            session.execute(
                text(
                    """
                    INSERT INTO drive_logs (date, goal_id, session_count)
                    VALUES (:date, :goal_id, :session_count)
                    ON CONFLICT(date, goal_id) DO UPDATE SET
                        session_count = excluded.session_count
                    """
                ),
                {
                    "date": date,
                    "goal_id": goal_id,
                    "session_count": int(count),
                },
            )


def apply_focus_log(session: Session, payload: Any) -> None:
    if not isinstance(payload, list):
        return
    for row in payload:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        date = row["date"]
        ensure_daily_log(session, date)
        session.execute(
            text(
                """
                INSERT INTO focus_logs (date, minutes)
                VALUES (:date, :minutes)
                """
            ),
            {"date": date, "minutes": int(row.get("minutes") or 0)},
        )


def apply_ui_state(session: Session, export: dict[str, Any]) -> None:
    for src_key, dest_key in UI_KEY_MAP.items():
        if src_key not in export or export[src_key] is None:
            continue
        value = export[src_key]
        stored = value if isinstance(value, str) else dumps(value)
        session.execute(
            text(
                """
                INSERT INTO ui_state (key, value)
                VALUES (:key, :value)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            ),
            {"key": dest_key, "value": stored},
        )


def migrate(export: dict[str, Any], session: Session) -> None:
    seed_tasks(session)
    apply_progress_data(session, export.get("plan_progress_data"))
    apply_settings(session, export.get("plan_settings"))
    apply_history(session, export.get("plan_history"))
    apply_today_done(session, export.get("plan_today_done"))
    apply_three_tasks(session, export.get("plan_three_tasks"))
    apply_week_manual(session, export.get("plan_week_manual"))
    apply_drive_logs(session, export)
    apply_focus_log(session, export.get("plan_focus_log"))
    apply_ui_state(session, export)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate V1 localStorage JSON into SQLite")
    parser.add_argument("json_path", type=Path, help="V1 settings export JSON")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: backend/data/app.db or MYPLAN_DB_PATH)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.json_path.is_file():
        raise SystemExit(f"file not found: {args.json_path}")
    init_engine(args.db)
    export = load_export(args.json_path)
    with get_session() as session:
        migrate(export, session)
    print(f"migrated {args.json_path} -> SQLite")


if __name__ == "__main__":
    main()
