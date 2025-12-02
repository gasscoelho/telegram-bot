from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from pydantic import BaseModel
from telegram.ext import ContextTypes


class Kind(Enum):
    """Task type for Last War reminders."""

    TRUCK = "truck"
    BUILD = "build"
    RESEARCH = "research"
    TRAIN = "train"
    MINISTRY = "ministry"
    CUSTOM = "custom"
    LIST = "list"
    CANCEL = "cancel"


@dataclass
class LwContext:
    """User conversation context for Last War bot."""

    kind: Kind | None = None
    task_name: str | None = None  # free-form label
    value: timedelta | None = None  # duration (e.g., 2h) or server time (e.g., 17:09:08)
    lead_time: str | None = None  # early ping (e.g., 5m)


class ReminderRequest(BaseModel):
    """Request to schedule a reminder."""

    user_id: int
    chat_id: int
    kind: Kind
    task_name: str | None
    duration: timedelta
    lead_time: str | None = None
    webhook_url: str | None = None


def get_user_context(context: ContextTypes.DEFAULT_TYPE) -> LwContext:
    """Get or create the Last War context for the current user."""
    if context.user_data is None:
        context.user_data = {}
    ctx = context.user_data.get("lw_ctx")
    if not ctx:
        ctx = LwContext()
        context.user_data["lw_ctx"] = ctx
    return ctx
