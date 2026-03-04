"""
    python extract_demo.py --account ACC-001 \
        --transcript ../dataset/demo_calls/demo_001_aquaguard.txt
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from llm_client import extract_structured
from validate_schema import validate_memo
from generate_agent import build_agent_spec
from task_tracker import log_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MEMO_EXTRACTION_PROMPT = """
You are an AI systems analyst processing a client demo call transcript for Clara Answers.

Your task is to extract structured operational data from the transcript and return ONLY valid JSON.
Do not include any explanation, markdown, or text outside the JSON object.

If information is missing or unclear, do NOT invent it. Instead, add a clear question to
"questions_or_unknowns" describing what needs to be confirmed.

Return a JSON object matching this exact schema:

{{
  "account_id": "<string>",
  "company_name": "<string>",
  "office_address": "<string or null>",
  "business_hours": {{
    "monday": "<open-close or null>",
    "tuesday": "<open-close or null>",
    "wednesday": "<open-close or null>",
    "thursday": "<open-close or null>",
    "friday": "<open-close or null>",
    "saturday": "<open-close or null>",
    "sunday": "<open-close or null>",
    "timezone": "<string or null>",
    "notes": "<string or null>"
  }},
  "services_supported": ["<list of services>"],
  "emergency_definition": "<string describing what constitutes an emergency>",
  "emergency_routing_rules": [
    {{
      "condition": "<when this rule applies>",
      "action": "<what to do>",
      "phone_number": "<number or null>",
      "transfer_timeout_rings": <int or null>,
      "fallback_action": "<string or null>",
      "fallback_phone_number": "<string or null>"
    }}
  ],
  "non_emergency_routing_rules": [
    {{
      "condition": "<when this rule applies>",
      "action": "<what to do>",
      "phone_number": "<number or null>",
      "transfer_timeout_rings": <int or null>,
      "fallback_action": "<string or null>",
      "fallback_phone_number": "<string or null>"
    }}
  ],
  "call_transfer_rules": [
    {{
      "scenario": "<description>",
      "primary_transfer_to": "<destination name>",
      "primary_phone_number": "<number or null>",
      "timeout_rings": <int or null>,
      "fallback": "<string or null>"
    }}
  ],
  "integration_constraints": [
    {{
      "platform": "<name or null>",
      "connected": false,
      "notes": "<string or null>"
    }}
  ],
  "after_hours_flow_summary": "<string summarizing after-hours call handling>",
  "office_hours_flow_summary": "<string summarizing business-hours call handling>",
  "questions_or_unknowns": ["<list of unconfirmed items>"],
  "notes": ["<list of special instructions or observations>"],
  "version": "1",
  "extracted_at": "<ISO timestamp>"
}}

Account ID for this account: {account_id}

TRANSCRIPT:
{transcript}
"""


def get_output_dir(account_id: str, version: str) -> Path:
    base = Path(__file__).parent.parent / "outputs" / "accounts" / account_id / f"v{version}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_json(data: dict, path: Path) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved: %s", path)



def run_demo_pipeline(account_id: str, transcript_path: str, max_retries: int = 3) -> None:
    logger.info("=== DEMO PIPELINE START: %s ===", account_id)

    # --- Read transcript ---
    transcript_text = Path(transcript_path).read_text()
    logger.info("Loaded transcript: %s (%d chars)", transcript_path, len(transcript_text))

    # --- Extract memo with retry + validation ---
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    prompt = MEMO_EXTRACTION_PROMPT.format(
        account_id=account_id,
        transcript=transcript_text,
    )

    memo_dict = None
    for attempt in range(1, max_retries + 1):
        raw = extract_structured(prompt)
        raw["account_id"] = account_id
        raw["extracted_at"] = timestamp
        raw["version"] = "1"

        valid, memo_obj, err = validate_memo(raw)
        if valid:
            memo_dict = raw
            logger.info("Memo validation passed (attempt %d)", attempt)
            break
        else:
            logger.warning("Attempt %d: memo invalid — %s. Retrying...", attempt, err)
            if attempt == max_retries:
                raise RuntimeError(f"Memo extraction failed after {max_retries} attempts: {err}")


    out_dir = get_output_dir(account_id, "1")
    save_json(memo_dict, out_dir / "memo.json")


    agent_spec = build_agent_spec(memo_dict, version="1")
    save_json(agent_spec, out_dir / "agent_spec.json")

    log_run(
        account_id=account_id,
        company_name=memo_dict.get("company_name", "Unknown"),
        stage="demo",
        version="1",
        status="success",
        outputs=[str(out_dir / "memo.json"), str(out_dir / "agent_spec.json")],
    )

    logger.info("=== DEMO PIPELINE COMPLETE: %s ===", account_id)
    print(f"\n✅  Demo pipeline complete for {account_id}")
    print(f"   Memo v1:       {out_dir / 'memo.json'}")
    print(f"   Agent spec v1: {out_dir / 'agent_spec.json'}")



# CLI SUPPORT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Stage 1 demo extraction pipeline.")
    parser.add_argument("--account", required=True, help="Account ID (e.g. ACC-001)")
    parser.add_argument("--transcript", required=True, help="Path to demo call transcript")
    parser.add_argument("--retries", type=int, default=3, help="Max extraction retries")
    args = parser.parse_args()

    run_demo_pipeline(
        account_id=args.account,
        transcript_path=args.transcript,
        max_retries=args.retries,
    )
