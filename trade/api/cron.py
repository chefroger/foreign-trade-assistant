"""
Trade AI Assistant — Cron 任务 API。

读取 Hermes cron 输出和 jobs.json，返回今日任务清单及已激活任务列表。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, date
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["cron"])

_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
_CRON_OUTPUT = _HERMES_HOME / "cron" / "output"
_JOBS_FILE = _HERMES_HOME / "cron" / "jobs.json"


@router.get("/cron/today")
def get_today_cron():
    """返回今日 cron 任务清单（已执行 + 待执行）。"""
    today = date.today().isoformat()

    standard_tasks = [
        {"name": "早安简报", "time": "09:00"},
        {"name": "邮件处理与跟进", "time": "09:00-10:30"},
        {"name": "精准加人 (LinkedIn)", "time": "10:00-11:30"},
        {"name": "评论互动与私信致谢", "time": "11:30-12:00"},
        {"name": "LinkedIn 内容发布", "time": "15:30"},
        {"name": "B2B 平台检查", "time": "15:30-17:00"},
        {"name": "客户开发", "time": "13:30-15:30"},
        {"name": "每日工作总结", "time": "17:00"},
    ]

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    completed = []
    pending = []

    for task in standard_tasks:
        task_time = task["time"].split("-")[0] if "-" in task["time"] else task["time"]
        is_past = task_time <= current_time
        output = _find_cron_output(task["name"], today)

        if output:
            completed.append({
                "name": task["name"], "time": task["time"],
                "output": output[:300], "has_output": True,
            })
        elif is_past:
            pending.append({
                "name": task["name"], "time": task["time"],
                "scheduled": task_time, "missed": True,
            })
        else:
            pending.append({
                "name": task["name"], "time": task["time"],
                "scheduled": task_time, "missed": False,
            })

    return {"today": today, "current_time": current_time, "completed": completed, "pending": pending}


@router.get("/cron/jobs")
def get_active_jobs():
    """返回 Hermes cron 中已激活的定时任务列表。

    从 ~/.hermes/cron/jobs.json 读取，返回任务名称、调度时间、下次执行时间。
    """
    if not _JOBS_FILE.is_file():
        return []

    try:
        with open(_JOBS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    jobs = []
    for job_id, job in data.items():
        if not isinstance(job, dict):
            continue
        jobs.append({
            "id": job_id,
            "name": job.get("task_name", job.get("name", job_id)),
            "schedule": job.get("schedule", ""),
            "next_run": job.get("next_run_at", ""),
            "enabled": job.get("enabled", True),
            "deliver": job.get("deliver", "local"),
        })

    return jobs


def _find_cron_output(task_name: str, today: str) -> str | None:
    if not _CRON_OUTPUT.is_dir():
        return None
    for job_dir in sorted(_CRON_OUTPUT.iterdir(), reverse=True):
        if not job_dir.is_dir():
            continue
        for output_file in sorted(job_dir.glob("*.md"), reverse=True):
            try:
                content = output_file.read_text(encoding="utf-8")
                if task_name in content and today in output_file.stem[:10]:
                    return content
            except Exception:
                continue
    return None
