
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from deepdiff import DeepDiff

logger = logging.getLogger(__name__)


EXCLUDED_FIELDS = {"extracted_at", "version"}


def _clean_for_diff(memo: Dict[str, Any]) -> Dict[str, Any]:
    """Remove metadata fields that should not appear in the changelog."""
    return {k: v for k, v in memo.items() if k not in EXCLUDED_FIELDS}


def _format_path(path_str: str) -> str:
    """Convert DeepDiff path notation to readable field name."""

    import re
    parts = re.findall(r"\['([^']+)'\]|\[(\d+)\]", path_str)
    result = []
    for name, idx in parts:
        if name:
            result.append(name)
        elif idx:
            result.append(f"[{idx}]")
    return ".".join(result)


def _summarize_diff(diff: DeepDiff) -> List[Dict[str, Any]]:
    """Convert DeepDiff result into a list of readable change records."""
    changes = []

    # Values changed
    for path, change in diff.get("values_changed", {}).items():
        changes.append({
            "type": "updated",
            "field": _format_path(path),
            "old_value": change["old_value"],
            "new_value": change["new_value"],
        })

    # Items added to root dict
    for path, value in diff.get("dictionary_item_added", {}).items():
        changes.append({
            "type": "added",
            "field": _format_path(path),
            "new_value": value,
        })

    # Items removed from root dict
    for path, value in diff.get("dictionary_item_removed", {}).items():
        changes.append({
            "type": "removed",
            "field": _format_path(path),
            "old_value": value,
        })

    # Items added to lists
    for path, items in diff.get("iterable_item_added", {}).items():
        changes.append({
            "type": "list_item_added",
            "field": _format_path(path),
            "new_value": items,
        })

    # Items removed from lists
    for path, items in diff.get("iterable_item_removed", {}).items():
        changes.append({
            "type": "list_item_removed",
            "field": _format_path(path),
            "old_value": items,
        })

    # Type changes
    for path, change in diff.get("type_changes", {}).items():
        changes.append({
            "type": "type_changed",
            "field": _format_path(path),
            "old_value": change["old_value"],
            "new_value": change["new_value"],
        })

    return changes


def generate_changelog(
    memo_v1: Dict[str, Any],
    memo_v2: Dict[str, Any],
    account_id: str,
) -> Dict[str, Any]:
    """
    Compare v1 and v2 memos and return a changelog dict.
    """
    clean_v1 = _clean_for_diff(memo_v1)
    clean_v2 = _clean_for_diff(memo_v2)

    diff = DeepDiff(clean_v1, clean_v2, ignore_order=True, verbose_level=2)
    changes = _summarize_diff(diff)

    changelog = {
        "account_id": account_id,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "v1_extracted_at": memo_v1.get("extracted_at"),
        "v2_extracted_at": memo_v2.get("extracted_at"),
        "total_changes": len(changes),
        "changes": changes,
        "summary": (
            f"{len(changes)} change(s) detected between v1 and v2."
            if changes
            else "No operational changes detected between v1 and v2."
        ),
    }

    logger.info("Changelog generated: %d changes for account %s", len(changes), account_id)
    return changelog

# CLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate changelog between memo v1 and v2.")
    parser.add_argument("--v1", required=True, help="Path to memo v1 JSON")
    parser.add_argument("--v2", required=True, help="Path to memo v2 JSON")
    parser.add_argument("--output", required=True, help="Output path for changelog.json")
    parser.add_argument("--account", default="UNKNOWN", help="Account ID label")
    args = parser.parse_args()

    with open(args.v1) as f:
        v1 = json.load(f)
    with open(args.v2) as f:
        v2 = json.load(f)

    changelog = generate_changelog(v1, v2, args.account)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(changelog, f, indent=2)

    print(f"✅  Changelog saved to: {out}")
    print(f"   Total changes: {changelog['total_changes']}")
