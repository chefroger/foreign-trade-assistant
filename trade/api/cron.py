"""
Trade AI Assistant — Cron 任务输出读取 API。

读取 Hermes cron 输出目录，返回今日任务清单及其执行状态。
"""

from __future__ import annotations

import os
from datetime import datetime, date
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["cron"])

# cron 输出目录
_CRON_OUTPUT = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "cron" / "output"


@router.get("/cron/today")
def get_today_cron():
    """返回今日 cron 任务清单（已执行 + 待执行）。

    从 ~/.hermes/cron/output/ 读取今天已执行的 cron 输出文件，
    结合 7 个标准任务的调度时间判断哪些尚未执行。

    Returns:
        {
            "today": "2026-05-15",
            "completed": [{"name": "...", "time": "08:00", "output": "..."}, ...],
            "pending": [{"name": "...", "time": "09:30", "scheduled": "09:30"}, ...],
        }
    """
    today = date.today().isoformat()

    # 7 个标准任务（与前端 tasks 视图一致）
    standard_tasks = [
        {"name": "早安简报", "time": "08:00"},
        {"name": "LinkedIn 内容发布", "time": "09:30"},
        {"name": "欧洲客户开发信", "time": "10:00"},
        {"name": "B2B 平台数据检查", "time": "11:00"},
        {"name": "社媒内容发布", "time": "14:00"},
        {"name": "北美客户开发信", "time": "16:00"},
        {"name": "每日工作总结", "time": "17:30"},
    ]

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    completed = []
    pending = []

    for task in standard_tasks:
        task_time = task["time"]
        is_past = task_time <= current_time

        # 查找该任务的 cron 输出
        output = _find_cron_output(task["name"], today)

        if output:
            completed.append({
                "name": task["name"],
                "time": task_time,
                "output": output[:300],  # 截断避免过大
                "has_output": True,
            })
        elif is_past:
            # 已过调度时间但无输出 → 可能未执行
            pending.append({
                "name": task["name"],
                "time": task_time,
                "scheduled": task_time,
                "missed": True,
            })
        else:
            pending.append({
                "name": task["name"],
                "time": task_time,
                "scheduled": task_time,
                "missed": False,
            })

    return {
        "today": today,
        "current_time": current_time,
        "completed": completed,
        "pending": pending,
    }


def _find_cron_output(task_name: str, today: str) -> str | None:
    """在 cron/output/ 目录下查找特定任务的今日输出。"""
    if not _CRON_OUTPUT.is_dir():
        return None

    # 遍历子目录，匹配最新的输出文件
    for job_dir in sorted(_CRON_OUTPUT.iterdir(), reverse=True):
        if not job_dir.is_dir():
            continue
        for output_file in sorted(job_dir.glob("*.md"), reverse=True):
            try:
                content = output_file.read_text(encoding="utf-8")
                # 检查是否包含该任务名称且为今天的输出
                if task_name in content and today in output_file.stem[:10]:
                    return content
            except Exception:
                continue
    return None
