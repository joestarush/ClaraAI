"""
    python extract_onboarding.py --account ACC-001 \
        --transcript ../dataset/onboarding_calls/onboarding_001_aquaguard.txt
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from llm_client import extract_structured
from validate_schema import validate_memo
from generate_agent import build_agent_spec
from generate_diff import generate_changelog
from task_tracker import log_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Prompt for extracting the updated memo based on the onboarding call and existing v1 memo

PATCH_EXTRACTION_PROMPT = """
You are an AI systems analyst processing a client onboarding call transcript for Clara Answers.

You are given:
1. The EXISTING v1 memo (extracted from a previous demo call)
2. The NEW onboarding call transcript

Your task is to produce an UPDATED memo that:
- Preserves all confirmed information from v1
- Updates any fields that were uncertain or missing in v1 with confirmed values from the onboarding call
- Adds any NEW information from the onboarding call
- Removes items from "questions_or_unknowns" that have now been answered
- Adds any NEW questions to "questions_or_unknowns" if new gaps emerged

Return ONLY valid JSON. Do not include any explanation or markdown.

The JSON must follow this exact schema:
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
  "services_supported": ["<list>"],
  "emergency_definition": "<string>",
  "emergency_routing_rules": [
    {{
      "condition": "<string>",
      "action": "<string>",
      "phone_number": "<string or null>",
      "transfer_timeout_rings": <int or null>,
      "fallback_action": "<string or null>",
      "fallback_phone_number": "<string or null>"
    }}
  ],
  "non_emergency_routing_rules": [
    {{
      "condition": "<string>",
      "action": "<string>",
      "phone_number": "<string or null>",
      "transfer_timeout_rings": <int or null>,
      "fallback_action": "<string or null>",
      "fallback_phone_number": "<string or null>"
    }}
  ],
  "call_transfer_rules": [
    {{
      "scenario": "<string>",
      "primary_transfer_to": "<string>",
      "primary_phone_number": "<string or null>",
      "timeout_rings": <int or null>,
      "fallback": "<string or null>"
    }}
  ],
  "integration_constraints": [
    {{
      "platform": "<string or null>",
      "connected": false,
      "notes": "<string or null>"
    }}
  ],
  "after_hours_flow_summary": "<string>",
  "office_hours_flow_summary": "<string>",
  "questions_or_unknowns": ["<list — only remaining open items>"],
  "notes": ["<list>"],
  "version": "2",
  "extracted_at": "<ISO timestamp>"
}}

---
EXISTING V1 MEMO:
{memo_v1_json}

---
ONBOARDING CALL TRANSCRIPT:
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


def load_memo_v1(account_id: str) -> dict:
    memo_path = (
        Path(__file__).parent.parent / "outputs" / "accounts" / account_id / "v1" / "memo.json"
    )
    if not memo_path.exists():
        raise FileNotFoundError(
            f"v1 memo not found at {memo_path}. "
            f"Run extract_demo.py for account {account_id} first."
        )
    with open(memo_path) as f:
        return json.load(f)



def run_onboarding_pipeline(
    account_id: str, transcript_path: str, max_retries: int = 3
) -> None:
    logger.info("=== ONBOARDING PIPELINE START: %s ===", account_id)


    memo_v1 = load_memo_v1(account_id)
    logger.info("Loaded v1 memo for %s", account_id)

    transcript_text = Path(transcript_path).read_text()
    logger.info("Loaded transcript: %s (%d chars)", transcript_path, len(transcript_text))


    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    prompt = PATCH_EXTRACTION_PROMPT.format(
        memo_v1_json=json.dumps(memo_v1, indent=2),
        transcript=transcript_text,
    )

    memo_v2_dict = None
    for attempt in range(1, max_retries + 1):
        raw = extract_structured(prompt)
        raw["account_id"] = account_id
        raw["extracted_at"] = timestamp
        raw["version"] = "2"

        valid, memo_obj, err = validate_memo(raw)
        if valid:
            memo_v2_dict = raw
            logger.info("Memo v2 validation passed (attempt %d)", attempt)
            break
        else:
            logger.warning("Attempt %d: memo v2 invalid — %s. Retrying...", attempt, err)
            if attempt == max_retries:
                raise RuntimeError(f"Memo v2 extraction failed after {max_retries} attempts: {err}")


    out_dir_v2 = get_output_dir(account_id, "2")
    save_json(memo_v2_dict, out_dir_v2 / "memo.json")

    agent_spec_v2 = build_agent_spec(memo_v2_dict, version="2")
    save_json(agent_spec_v2, out_dir_v2 / "agent_spec.json")

    changelog = generate_changelog(memo_v1, memo_v2_dict, account_id)
    save_json(changelog, out_dir_v2 / "changelog.json")

    log_run(
        account_id=account_id,
        company_name=memo_v2_dict.get("company_name", "Unknown"),
        stage="onboarding",
        version="2",
        status="success",
        outputs=[
            str(out_dir_v2 / "memo.json"),
            str(out_dir_v2 / "agent_spec.json"),
            str(out_dir_v2 / "changelog.json"),
        ],
        notes=f"{changelog.get('total_changes', 0)} changes from v1 to v2",
    )

    logger.info("=== ONBOARDING PIPELINE COMPLETE: %s ===", account_id)
    print(f"\n✅  Onboarding pipeline complete for {account_id}")
    print(f"   Memo v2:       {out_dir_v2 / 'memo.json'}")
    print(f"   Agent spec v2: {out_dir_v2 / 'agent_spec.json'}")
    print(f"   Changelog:     {out_dir_v2 / 'changelog.json'}")


# CLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Stage 2 onboarding extraction pipeline.")
    parser.add_argument("--account", required=True, help="Account ID (e.g. ACC-001)")
    parser.add_argument("--transcript", required=True, help="Path to onboarding call transcript")
    parser.add_argument("--retries", type=int, default=3, help="Max extraction retries")
    args = parser.parse_args()

    run_onboarding_pipeline(
        account_id=args.account,
        transcript_path=args.transcript,
        max_retries=args.retries,
    )
