"""Telegram handlers for Last War bot."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.shared.utils.duration import format_duration, parse_duration

from .conversation.prompts import (
    ask_custom_task_prompt,
    ask_duration_prompt,
    ask_heads_up_prompt,
    ask_server_time_prompt,
    send_invalid_duration_prompt,
    send_invalid_nl_prompt,
)
from .conversation.states import (
    CHOOSING,
    ENTERING_CUSTOM_TASK,
    ENTERING_DURATION,
    ENTERING_HEADS_UP,
)
from .messages import Messages, Messenger
from .models import Kind, get_user_context
from .nl.interpreter import interpret_natural_command

logger = logging.getLogger(__name__)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry command: /lw — show task selection menu."""
    if not update.message:
        return ConversationHandler.END
    kb = [
        [
            InlineKeyboardButton("🚚 Truck", callback_data="lw:truck"),
            InlineKeyboardButton("🏗 Build", callback_data="lw:build"),
            InlineKeyboardButton("🔬 Research", callback_data="lw:research"),
        ],
        [
            InlineKeyboardButton("🪖 Train", callback_data="lw:train"),
            InlineKeyboardButton("🏛 Ministry", callback_data="lw:ministry"),
            InlineKeyboardButton("✏️ Custom", callback_data="lw:custom"),
        ],
        [
            InlineKeyboardButton("📝 List", callback_data="lw:list"),
            InlineKeyboardButton("🗑 Cancel", callback_data="lw:cancel"),
        ],
    ]
    messenger = Messenger(context=context)
    await messenger.reply(
        update,
        msg=Messages.WELCOME.value,
        reply_markup=InlineKeyboardMarkup(kb),
        store_key="menu",
    )
    return CHOOSING


async def on_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle task selection from menu."""
    query = update.callback_query
    if not query or not query.message or not query.data:
        return ConversationHandler.END

    await query.answer()

    tag = query.data.split(":", 1)[1]  # e.g., 'truck', 'build', ...
    user_ctx = get_user_context(context)
    messenger = Messenger(context=context)

    # TODO: Complete implementation -- It should list the scheduled reminders
    if tag == "list":
        await messenger.append_and_close(store_key="menu", append_line="List")
        await messenger.send(update, msg="📋 List is a stub in this MVP.")
        return CHOOSING

    # TODO: Complete implementation -- It should unschedule a reminder
    if tag == "cancel":
        await messenger.append_and_close(store_key="menu", append_line="Cancel")
        await messenger.send(update, msg="🗑 Cancel is a stub in this MVP.")
        return CHOOSING

    kind_mapping = {
        "truck": Kind.TRUCK,
        "build": Kind.BUILD,
        "research": Kind.RESEARCH,
        "train": Kind.TRAIN,
        "ministry": Kind.MINISTRY,
        "custom": Kind.CUSTOM,
    }

    # Set kind
    user_ctx.kind = kind_mapping.get(tag)
    if not user_ctx.kind:
        await messenger.append_and_close(store_key="menu", append_line="<unknown>")
        return ConversationHandler.END

    # Mark choice on the welcome message and close its buttons
    choice_value = user_ctx.kind.value.capitalize()
    await messenger.append_and_close(
        store_key="menu",
        append_line=f"`{choice_value}`",
    )

    if user_ctx.kind == Kind.CUSTOM:
        return await ask_custom_task_prompt(messenger, update=update)

    if user_ctx.kind == Kind.MINISTRY:
        return await ask_server_time_prompt(messenger, update=update)

    return await ask_duration_prompt(messenger, update=update)


async def on_enter_custom_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom task name input."""
    msg = update.message
    if not msg or not msg.text:
        return ConversationHandler.END
    user_ctx = get_user_context(context)
    title = msg.text.strip()
    user_ctx.task_name = title
    messenger = Messenger(context=context)
    await messenger.append_and_close(store_key="custom_task", append_line=f"`{title}`")
    return await ask_duration_prompt(messenger, update=update)


async def on_enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle duration input (from button or text)."""
    duration = None
    query = update.callback_query

    if query:
        if not query.data:
            return ConversationHandler.END
        await query.answer()
        _, _, val = query.data.partition("lw:dur:")
        duration = val
    else:
        msg = update.message
        if not msg or not msg.text:
            return ConversationHandler.END
        duration = msg.text.strip()

    messenger = Messenger(context=context)
    user_ctx = get_user_context(context)
    try:
        user_ctx.value = parse_duration(duration)
    except ValueError:
        return await send_invalid_duration_prompt(messenger, update=update)

    await messenger.append_and_close(
        store_key="duration", append_line=f"`{format_duration(user_ctx.value)}`"
    )
    return await ask_heads_up_prompt(messenger, update=update)


async def on_enter_heads_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle heads-up/lead time input and complete the reminder setup."""
    user_ctx = get_user_context(context)
    query = update.callback_query

    # Determine "lead_time" value
    if query:
        if not query.data or not query.message:
            return ConversationHandler.END
        await query.answer()
        _, _, val = query.data.partition("lw:lead_time:")
        user_ctx.lead_time = None if val == "skip" else val
    else:
        msg = update.message
        if not msg or not msg.text:
            return ConversationHandler.END
        user_ctx.lead_time = msg.text.strip()

    headsup = user_ctx.lead_time or "No"
    messenger = Messenger(context=context)
    await messenger.append_and_close(store_key="lead", append_line=f"`{headsup}`")

    # Prepare summary
    kind_label = "Unknown"
    if user_ctx.kind == Kind.CUSTOM and user_ctx.task_name:
        kind_label = user_ctx.task_name
    elif user_ctx.kind:
        kind_label = user_ctx.kind.value
    value = format_duration(user_ctx.value) if user_ctx.value else "N/A"
    lead_time = user_ctx.lead_time or "None"

    # Build summary
    summary = (
        "✅ Scheduled (MVP)\n"
        f"• Task: {kind_label.capitalize()}\n"
        f"• Duration: {value}\n"
        f"• Heads-up: {lead_time}\n"
    )
    await messenger.send(
        update,
        msg=messenger.escape_md_v2(summary),
    )

    # Clear user context
    if hasattr(context, "user_data") and context.user_data:
        context.user_data.pop("lw_ctx", None)
        context.user_data.pop("lw_msgs", None)

    return ConversationHandler.END


async def on_natural_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language command input."""
    msg = update.message
    if not msg or not msg.text:
        return CHOOSING

    messenger = Messenger(context=context)
    text = msg.text.strip()

    try:
        parsed = await interpret_natural_command(text)
    except Exception as e:
        return await send_invalid_nl_prompt(
            messenger,
            update=update,
            error_msg=str(e),
        )

    if not parsed:
        return await send_invalid_nl_prompt(messenger, update=update)

    user_ctx = get_user_context(context)
    user_ctx.kind = parsed.kind or Kind.CUSTOM
    user_ctx.task_name = parsed.task_name
    user_ctx.value = parsed.to_timedelta()

    # TODO: Consider adding a confirmation step before going to the next step

    # Skip the "choose kind" and "enter duration" steps,
    # and jump straight to the heads-up state.
    return await ask_heads_up_prompt(messenger, update=update)


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation cancellation."""
    if hasattr(context, "user_data") and isinstance(context.user_data, dict):
        context.user_data.pop("lw_ctx", None)
        context.user_data.pop("lw_msgs", None)
    if update.message:
        await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def register(app: Application):
    """
    Register Last War bot handlers.

    Usage: from src.bots.lastwar import register as register_lastwar; register_lastwar(ptb)
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("lw", on_start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(on_choose, pattern=r"^lw:(?!dur:|lead_time:)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_natural_command),
            ],
            ENTERING_CUSTOM_TASK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_enter_custom_task),
            ],
            ENTERING_DURATION: [
                CallbackQueryHandler(on_enter_duration, pattern=r"^lw:dur:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_enter_duration),
            ],
            ENTERING_HEADS_UP: [
                CallbackQueryHandler(on_enter_heads_up, pattern=r"^lw:lead_time:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_enter_heads_up),
            ],
        },
        fallbacks=[CommandHandler("cancel", on_cancel)],
        name="lastwar_mvp",
        persistent=False,
    )
    app.add_handler(conv)
