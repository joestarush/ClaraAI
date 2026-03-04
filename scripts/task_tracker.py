
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).parent.parent / "outputs" / "run_log.json"


def _load_log() -> list:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        with open(LOG_PATH) as f:
            return json.load(f)
    return []


def _save_log(entries: list) -> None:
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def log_run(
    account_id: str,
    company_name: str,
    stage: str,          # "demo" or "onboarding"
    version: str,        # "1" or "2"
    status: str,         # "success" or "failed"
    outputs: list = None,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Log a pipeline run. Creates a new entry and appends to run_log.json.
    Acts as the task tracker item for this account run.
    """
    entry = {
        "task_id": f"{account_id}-v{version}-{stage}",
        "account_id": account_id,
        "company_name": company_name,
        "stage": stage,
        "version": version,
        "status": status,
        "outputs": outputs or [],
        "notes": notes,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    entries = _load_log()
    entries = [e for e in entries if e.get("task_id") != entry["task_id"]]
    entries.append(entry)
    _save_log(entries)

    logger.info("Task logged: %s [%s]", entry["task_id"], status)
    return entry
