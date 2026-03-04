"""
    python run_all.py                  # Run demo + onboarding for all accounts
    python run_all.py --stage demo     # Demo only
    python run_all.py --stage onboarding  # Onboarding only (requires demo run first)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from extract_demo import run_demo_pipeline
from extract_onboarding import run_onboarding_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent

ACCOUNTS = [
    {
        "account_id": "ACC-001",
        "demo_transcript": BASE / "dataset/demo_calls/demo_001_aquaguard.txt",
        "onboarding_transcript": BASE / "dataset/onboarding_calls/onboarding_001_aquaguard.txt",
    },
    {
        "account_id": "ACC-002",
        "demo_transcript": BASE / "dataset/demo_calls/demo_002_shieldalarm.txt",
        "onboarding_transcript": BASE / "dataset/onboarding_calls/onboarding_002_shieldalarm.txt",
    },
    {
        "account_id": "ACC-003",
        "demo_transcript": BASE / "dataset/demo_calls/demo_003_voltedge.txt",
        "onboarding_transcript": BASE / "dataset/onboarding_calls/onboarding_003_voltedge.txt",
    },
    {
        "account_id": "ACC-004",
        "demo_transcript": BASE / "dataset/demo_calls/demo_004_coolflow.txt",
        "onboarding_transcript": BASE / "dataset/onboarding_calls/onboarding_004_coolflow.txt",
    },
    {
        "account_id": "ACC-005",
        "demo_transcript": BASE / "dataset/demo_calls/demo_005_firesafe.txt",
        "onboarding_transcript": BASE / "dataset/onboarding_calls/onboarding_005_firesafe.txt",
    },
]


def run_demo_stage() -> None:
    print("\n" + "=" * 60)
    print("STAGE 1: DEMO PIPELINE")
    print("=" * 60)
    for acct in ACCOUNTS:
        try:
            run_demo_pipeline(
                account_id=acct["account_id"],
                transcript_path=str(acct["demo_transcript"]),
            )
        except Exception as exc:
            logger.error("Demo pipeline failed for %s: %s", acct["account_id"], exc)


def run_onboarding_stage() -> None:
    print("\n" + "=" * 60)
    print("STAGE 2: ONBOARDING PIPELINE")
    print("=" * 60)
    for acct in ACCOUNTS:
        try:
            run_onboarding_pipeline(
                account_id=acct["account_id"],
                transcript_path=str(acct["onboarding_transcript"]),
            )
        except Exception as exc:
            logger.error("Onboarding pipeline failed for %s: %s", acct["account_id"], exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run all demo and onboarding pipelines.")
    parser.add_argument(
        "--stage",
        choices=["demo", "onboarding", "all"],
        default="all",
        help="Which stage to run (default: all)",
    )
    args = parser.parse_args()

    if args.stage in ("demo", "all"):
        run_demo_stage()

    if args.stage in ("onboarding", "all"):
        run_onboarding_stage()

    print("\n✅  All pipelines complete.")
