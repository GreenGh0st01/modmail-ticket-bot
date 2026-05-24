from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, TypedDict


class AttachmentPayload(TypedDict):
    filename: str
    url: str


class MessagePayload(TypedDict):
    content: str
    attachments: List[AttachmentPayload]
    created_at: datetime


class TicketTopicData(TypedDict):
    user_id: int
    ticket_type: str
    claimer_id: Optional[int]


@dataclass
class ModmailState:
    user_to_channel: Dict[int, int] = field(default_factory=dict)
    channel_to_user: Dict[int, int] = field(default_factory=dict)
    claimed_by: Dict[int, int] = field(default_factory=dict)
    blocked_users: Set[int] = field(default_factory=set)
    pending_messages: Dict[int, List[MessagePayload]] = field(default_factory=dict)
    ticket_logs: Dict[int, List[str]] = field(default_factory=dict)
