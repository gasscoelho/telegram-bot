import logging
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram._utils.types import ReplyMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

from bot.utils.duration import format_duration, parse_duration

logger = logging.getLogger(__name__)

# Conversation states
CHOOSING, ENTERING_CUSTOM_TASK, ENTERING_DURATION, ENTERING_HEADS_UP = range(4)


class Messages(Enum):
    WELCOME = "What would you like to be reminded about?"
    DURATION_QUESTION = "When should the reminder go off?"
    DURATION_EXAMPLE = "(e.g. 2h, 1h30m, or tap below)"
    DURATION_ERROR = "The duration you sent is not valid"
    DURATION_ERROR_EXAMPLE = "Please, try formats like 2h, 1d7:04, or 30m."
    HEADS_UP_QUESTION = "Heads-up before start?"
    SERVER_TIME_ASK = "Inform the server time shown in-game:"
    SERVER_TIME_EXAMPLE = "(e.g., 8-11-2025 17:09 or 17:09)"
    CUSTOM_TASK_ASK = "Inform the task name:"


# What the user selected
class Kind(Enum):
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
    kind: Kind | None = None
    task_name: str | None = None  # free-form label
    value: timedelta | None = (
        None  # duration (e.g., 2h) or server time (e.g., 17:09:08)
    )
    lead_time: str | None = None  # early ping (e.g., 5m)


@dataclass
class Messenger:
    context: ContextTypes.DEFAULT_TYPE
    header: str = "⚔️ Last War Bot\n\n"
    parse_mode: ParseMode = ParseMode.MARKDOWN_V2
    with_header: bool = True

    def _get_msg_store(self) -> dict:
        if self.context.user_data is None:
            self.context.user_data = {}
        store = self.context.user_data.get("lw_msgs")
        if not store:
            store = {}
            self.context.user_data["lw_msgs"] = store
        return store

    def _save_msg_sent(
        self,
        store_key: str,
        msg: str,
        chat_id: int,
        message_id: int,
    ) -> None:
        store = self._get_msg_store()
        store[store_key] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
        }

    def _get_chat_id(self, update: Update):
        chat = update.effective_chat
        return chat.id if chat else None

    def escape_md_v2(self, s: str) -> str:
        return escape_markdown(s, version=2)

    async def send(
        self,
        update: Update,
        msg: str,
        reply_markup: ReplyMarkup | None = None,
        store_key: str | None = None,
        store: bool = True,
    ):
        """Send a message with optional header + auto-store metadata."""
        chat_id = self._get_chat_id(update)
        if chat_id is None:
            return None
        wire_text = (f"*{self.header}*" if self.with_header else "") + msg
        sent = await self.context.bot.send_message(
            chat_id=chat_id,
            text=wire_text,
            reply_markup=reply_markup,
            parse_mode=self.parse_mode,
        )
        if store and store_key:
            self._save_msg_sent(
                store_key=store_key,
                msg=wire_text,
                chat_id=sent.chat_id,
                message_id=sent.message_id,
            )
        return sent

    async def reply(
        self,
        update: Update,
        msg: str,
        reply_markup: ReplyMarkup | None = None,
        store_key: str | None = None,
        store: bool = True,
    ):
        if not update.message:
            return ConversationHandler.END
        wire_text = (f"*{self.header}*" if self.with_header else "") + msg
        sent = await update.message.reply_text(
            wire_text,
            reply_markup=reply_markup,
            parse_mode=self.parse_mode,
        )
        if store and store_key:
            self._save_msg_sent(
                store_key=store_key,
                msg=wire_text,
                chat_id=sent.chat_id,
                message_id=sent.message_id,
            )

    async def append_and_close(self, store_key: str, append_line: str):
        """Append a line to a stored message (e.g., previously sent) and remove its buttons if any."""
        try:
            store = self._get_msg_store()
            meta = store.get(store_key)
            if not meta:
                return
            chat_id = meta["chat_id"]
            message_id = meta["message_id"]
            base_text = meta["text"]  # stored raw
            new_text = f"{base_text}\n\n{append_line}"
            await self.context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_text,
                reply_markup=None,
                parse_mode=self.parse_mode,
            )
            meta["text"] = new_text
        except Exception as e:
            logger.warning(f"Failed to edit/close message '{store_key}': {e}")


def _get_user_ctx(context: ContextTypes.DEFAULT_TYPE) -> LwContext:
    if context.user_data is None:
        context.user_data = {}
    ctx = context.user_data.get("lw_ctx")
    if not ctx:
        ctx = LwContext()
        context.user_data["lw_ctx"] = ctx
    return ctx


async def ask_duration_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "duration",
):
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


async def ask_heads_up_prompt(
    messenger: Messenger,
    update: Update,
    store_key: str = "lead",
):
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
    prompt = Messages.CUSTOM_TASK_ASK.value
    await messenger.send(
        update,
        msg=prompt,
        store_key=store_key,
    )
    return ENTERING_CUSTOM_TASK


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry command: /lw — pops a menu."""
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
    query = update.callback_query
    if not query or not query.message or not query.data:
        return ConversationHandler.END

    await query.answer()

    tag = query.data.split(":", 1)[1]  # e.g., 'truck', 'build', ...
    user_ctx = _get_user_ctx(context)
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
    msg = update.message
    if not msg or not msg.text:
        return ConversationHandler.END
    user_ctx = _get_user_ctx(context)
    title = msg.text.strip()
    user_ctx.task_name = title
    messenger = Messenger(context=context)
    await messenger.append_and_close(store_key="custom_task", append_line=f"`{title}`")
    return await ask_duration_prompt(messenger, update=update)


async def on_enter_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_ctx = _get_user_ctx(context)
    try:
        user_ctx.value = parse_duration(duration)
    except ValueError:
        return await send_invalid_duration_prompt(messenger, update=update)

    await messenger.append_and_close(
        store_key="duration", append_line=f"`{format_duration(user_ctx.value)}`"
    )
    return await ask_heads_up_prompt(messenger, update=update)


async def on_enter_heads_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ctx = _get_user_ctx(context)
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


async def on_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(context, "user_data") and isinstance(context.user_data, dict):
        context.user_data.pop("lw_ctx", None)
        context.user_data.pop("lw_msgs", None)
    if update.message:
        await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def register(app: Application):
    """
    Registers the /lw conversation (UX-only MVP; no scheduler).
    Usage: in main.py -> from bot.lastwar import register as register_lastwar; register_lastwar(ptb)
    """
    conv = ConversationHandler(
        entry_points=[CommandHandler("lw", on_start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(on_choose, pattern=r"^lw:(?!dur:|lead_time:)")
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
