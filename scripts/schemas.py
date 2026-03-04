"""
schemas.py — Pydantic models for Account Memo and Agent Spec validation.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator

# Sub-models


class BusinessHours(BaseModel):
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None


class RoutingRule(BaseModel):
    condition: Optional[str] = None
    action: Optional[str] = None
    phone_number: Optional[str] = None
    transfer_timeout_rings: Optional[int] = None
    fallback_action: Optional[str] = None
    fallback_phone_number: Optional[str] = None

    @field_validator("condition", "action", "fallback_action", "fallback_phone_number",
                     "phone_number", mode="before")
    @classmethod
    def coerce_to_str(cls, v):
        """Coerce any non-string value (list, int, None) to string or None."""
        if v is None:
            return None
        if isinstance(v, list):
            return ", ".join(str(i) for i in v) if v else None
        return str(v)

    @field_validator("transfer_timeout_rings", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class CallTransferRule(BaseModel):
    scenario: Optional[str] = None
    primary_transfer_to: Optional[str] = None
    primary_phone_number: Optional[str] = None
    timeout_rings: Optional[int] = None
    fallback: Optional[str] = None

    @field_validator("scenario", "primary_transfer_to", "primary_phone_number",
                     "fallback", mode="before")
    @classmethod
    def coerce_to_str(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return ", ".join(str(i) for i in v) if v else None
        return str(v)

    @field_validator("timeout_rings", mode="before")
    @classmethod
    def coerce_to_int(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class IntegrationConstraint(BaseModel):
    platform: Optional[str] = None
    connected: bool = False
    notes: Optional[str] = None

# Account Memo Schema


class AccountMemo(BaseModel):
    account_id: str
    company_name: str
    office_address: Optional[str] = None
    business_hours: Optional[BusinessHours] = None
    services_supported: List[str] = Field(default_factory=list)
    emergency_definition: Optional[str] = None
    emergency_routing_rules: List[RoutingRule] = Field(default_factory=list)
    non_emergency_routing_rules: List[RoutingRule] = Field(default_factory=list)
    call_transfer_rules: List[CallTransferRule] = Field(default_factory=list)
    integration_constraints: List[IntegrationConstraint] = Field(default_factory=list)
    after_hours_flow_summary: Optional[str] = None
    office_hours_flow_summary: Optional[str] = None
    questions_or_unknowns: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    version: str = "1"
    extracted_at: Optional[str] = None

# Agent Spec Schema


class TransferProtocol(BaseModel):
    primary_number: Optional[str] = None
    timeout_rings: Optional[int] = None
    timeout_seconds: Optional[int] = None
    fallback_number: Optional[str] = None
    fallback_action: Optional[str] = None


class FallbackProtocol(BaseModel):
    action: str
    message_to_caller: Optional[str] = None


class ToolInvocation(BaseModel):
    tool_name: str
    trigger_condition: str
    note: str = "Do not mention this tool to the caller"


class AgentSpec(BaseModel):
    agent_name: str
    account_id: str
    voice_style: str = "professional-friendly"
    version: str = "1"
    system_prompt: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    tool_invocations: List[ToolInvocation] = Field(default_factory=list)
    transfer_protocol: Optional[TransferProtocol] = None
    fallback_protocol: Optional[FallbackProtocol] = None
    generated_at: Optional[str] = None
