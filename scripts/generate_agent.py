
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


def _format_business_hours(bh: Optional[Dict]) -> str:
    if not bh:
        return "Business hours not confirmed. See questions_or_unknowns."
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    lines = []
    for d in days:
        val = bh.get(d)
        if val:
            lines.append(f"  {d.capitalize()}: {val}")
    tz = bh.get("timezone", "")
    if tz:
        lines.append(f"  Timezone: {tz}")
    return "\n".join(lines) if lines else "Not confirmed."


def _format_routing(rules: list) -> str:
    if not rules:
        return "  No routing rules defined."
    lines = []
    for r in rules:
        line = f"  - {r.get('condition','')}: {r.get('action','')}"
        ph = r.get("phone_number") or r.get("primary_phone_number")
        if ph:
            line += f" → {ph}"
        timeout = r.get("transfer_timeout_rings") or r.get("timeout_rings")
        if timeout:
            line += f" (timeout: {timeout} rings)"
        fallback = r.get("fallback_action") or r.get("fallback")
        if fallback:
            line += f" | Fallback: {fallback}"
        lines.append(line)
    return "\n".join(lines)


def _build_system_prompt(memo: Dict[str, Any]) -> str:
    company = memo.get("company_name", "the company")
    emergency_def = memo.get("emergency_definition") or "Active safety hazard requiring immediate response."
    bh_str = _format_business_hours(memo.get("business_hours"))
    emergency_rules = _format_routing(
        memo.get("emergency_routing_rules", []) + memo.get("call_transfer_rules", [])
    )
    non_emergency_rules = _format_routing(memo.get("non_emergency_routing_rules", []))
    after_hours = memo.get("after_hours_flow_summary") or "Take a message and confirm next-business-day callback."
    office_hours = memo.get("office_hours_flow_summary") or "Route to main office line."
    notes = "\n".join(f"  - {n}" for n in memo.get("notes", [])) or "  None."
    unknowns = "\n".join(f"  - {q}" for q in memo.get("questions_or_unknowns", [])) or "  None."

    return f"""You are an AI voice receptionist for {company}, powered by Clara Answers.
Your role is to handle inbound calls professionally, collect the right information,
and route callers correctly based on the following operational rules.

Always be calm, clear, and professional. Never invent information.
If you do not know the answer, take a message and promise follow-up.

---
COMPANY: {company}
ADDRESS: {memo.get('office_address', 'Not on file')}
SERVICES: {', '.join(memo.get('services_supported', []))}

---
BUSINESS HOURS:
{bh_str}

---
EMERGENCY DEFINITION:
{emergency_def}

---
EMERGENCY ROUTING:
{emergency_rules}

---
NON-EMERGENCY ROUTING:
{non_emergency_rules}

---
OFFICE HOURS CALL FLOW:
1. Greet caller: "Thank you for calling {company}. How can I help you today?"
2. Ask for the purpose of the call.
3. Collect caller name and callback phone number.
4. Determine if the situation is an emergency using the definition above.
5. If EMERGENCY: immediately attempt transfer per emergency routing rules above.
   - If transfer fails: apologize, assure them a technician will call within 30 minutes,
     collect address, and log the call.
6. If NOT EMERGENCY: route per non-emergency rules above.
7. Ask if the caller needs anything else.
8. Close politely: "Thank you for calling {company}. Have a great day."

OFFICE HOURS SUMMARY: {office_hours}

---
AFTER-HOURS CALL FLOW:
1. Greet caller: "Thank you for calling {company}. Our office is currently closed.
   I'm here to help route your call."
2. Ask for the purpose of the call.
3. Ask: "Is this an emergency?"
4. If EMERGENCY: collect name, phone, and address. Attempt emergency transfer.
   - If transfer fails: apologize sincerely, assure follow-up within 30 minutes.
5. If NOT EMERGENCY: collect name, phone number, and a brief message.
   Confirm: "Someone from our team will follow up with you during business hours."
6. Ask if the caller needs anything else.
7. Close politely.

AFTER-HOURS SUMMARY: {after_hours}

---
SPECIAL INSTRUCTIONS:
{notes}

---
OPEN QUESTIONS (do not mention to callers):
{unknowns}
"""

# Main builder


def build_agent_spec(memo: Dict[str, Any], version: str = "1") -> Dict[str, Any]:
    """
    Build a Retell-style agent spec dict from a memo dict.
    """
    account_id = memo.get("account_id", "UNKNOWN")
    company = memo.get("company_name", "Unknown Company")
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"


    emergency_rules = memo.get("emergency_routing_rules", [])
    primary_number = None
    timeout_rings = None
    fallback_number = None
    if emergency_rules:
        first = emergency_rules[0]
        primary_number = first.get("phone_number")
        timeout_rings = first.get("transfer_timeout_rings")
        fallback_number = first.get("fallback_phone_number")

    spec = {
        "agent_name": f"{company} Voice Agent",
        "account_id": account_id,
        "voice_style": "professional-friendly",
        "version": version,
        "system_prompt": _build_system_prompt(memo),
        "variables": {
            "company_name": company,
            "office_address": memo.get("office_address"),
            "business_hours_timezone": (memo.get("business_hours") or {}).get("timezone"),
            "services": memo.get("services_supported", []),
        },
        "tool_invocations": [
            {
                "tool_name": "transfer_call",
                "trigger_condition": "Emergency confirmed and caller details collected",
                "note": "Do not mention this tool to the caller"
            },
            {
                "tool_name": "log_message",
                "trigger_condition": "Non-emergency after hours or transfer failure",
                "note": "Do not mention this tool to the caller"
            }
        ],
        "transfer_protocol": {
            "primary_number": primary_number,
            "timeout_rings": timeout_rings,
            "timeout_seconds": (timeout_rings * 15) if timeout_rings else None,
            "fallback_number": fallback_number,
            "fallback_action": (emergency_rules[0].get("fallback_action") if emergency_rules else None),
        },
        "fallback_protocol": {
            "action": "take_message",
            "message_to_caller": (
                "I wasn't able to connect you right now. I've noted your information "
                "and someone will follow up with you shortly."
            ),
        },
        "generated_at": timestamp,
    }
    return spec

# CLI


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate agent spec from memo JSON.")
    parser.add_argument("--memo", required=True, help="Path to memo.json")
    parser.add_argument("--version", default="1", help="Version string (default: 1)")
    parser.add_argument("--output", help="Output path (default: same dir as memo)")
    args = parser.parse_args()

    memo_path = Path(args.memo)
    with open(memo_path) as f:
        memo_data = json.load(f)

    spec = build_agent_spec(memo_data, version=args.version)

    out_path = Path(args.output) if args.output else memo_path.parent / "agent_spec.json"
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)

    print(f"✅  Agent spec saved to: {out_path}")
