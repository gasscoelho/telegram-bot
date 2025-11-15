"""Prompt builders for Last War bot conversation flow."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from ..messages import Messages, Messenger
from .states import ENTERING_CUSTOM_TASK, ENTERING_DURATION, ENTERING_HEADS_UP


async def ask_duration_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "duration",
):
    """Show duration selection prompt with quick-select buttons."""
    kb = [
        [
            InlineKeyboardButton("30m", callback_data="lw:dur:30m"),
            InlineKeyboardButton("1h", callback_data="lw:dur:1h"),
            InlineKeyboardButton("2h", callback_data="lw:dur:2h"),
        ]
    ]
    prompt = (
        f"{Messages.DURATION_QUESTION.value}\n"
        f"_{messenger.escape_md_v2(Messages.DURATION_EXAMPLE.value)}_"
    )
    await messenger.send(
        update,
        msg=prompt,
        store_key=store_key,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ENTERING_DURATION


async def ask_server_time_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "duration",
):
    """Show server time input prompt for ministry tasks."""
    prompt = f"{messenger.escape_md_v2(Messages.SERVER_TIME_ASK.value)}\n_{messenger.escape_md_v2(Messages.SERVER_TIME_EXAMPLE.value)}_"
    await messenger.send(
        update,
        msg=prompt,
        store_key=store_key,
    )
    return ENTERING_DURATION


async def send_invalid_duration_prompt(
    messenger: Messenger,
    update: Update,
):
    """Show error message for invalid duration input."""
    prompt = (
        f"{Messages.DURATION_ERROR.value}"
        f"{messenger.escape_md_v2('. ' + Messages.DURATION_ERROR_EXAMPLE.value)}"
    )
    await messenger.send(
        update,
        msg=prompt,
        store=False,
    )
    return ENTERING_DURATION


async def send_invalid_nl_prompt(
    messenger: Messenger, update: Update, error_msg: str | None = None
):
    """Show error message for invalid natural language input."""
    from .states import CHOOSING

    if error_msg:
        prompt = (
            f"There was an error while processing your text"
            f":\n\n{messenger.escape_md_v2(error_msg)}"
        )
    else:
        prompt = f"I couldn't understand that{messenger.escape_md_v2('. Please, try again.')}"
    await messenger.send(
        update,
        msg=prompt,
        store=False,
    )
    return CHOOSING


async def ask_heads_up_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "lead",
):
    """Show heads-up/lead time selection prompt."""
    kb = [
        [
            InlineKeyboardButton("1m", callback_data="lw:lead_time:1m"),
            InlineKeyboardButton("3m", callback_data="lw:lead_time:3m"),
            InlineKeyboardButton("5m", callback_data="lw:lead_time:5m"),
        ],
        [InlineKeyboardButton("No", callback_data="lw:lead_time:skip")],
    ]
    await messenger.send(
        update,
        msg=messenger.escape_md_v2(Messages.HEADS_UP_QUESTION.value),
        store_key=store_key,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ENTERING_HEADS_UP


async def ask_custom_task_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "custom_task",
):
    """Show custom task name input prompt."""

    prompt = Messages.CUSTOM_TASK_ASK.value
    await messenger.send(
        update,
        msg=prompt,
        store_key=store_key,
    )
    return ENTERING_CUSTOM_TASK
