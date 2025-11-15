import logging
from dataclasses import dataclass
from enum import Enum

from telegram import Update
from telegram._utils.types import ReplyMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)


class Messages(Enum):
    """UI message templates for Last War bot."""

    WELCOME = "What would you like to be reminded about?"
    DURATION_QUESTION = "When should the reminder go off?"
    DURATION_EXAMPLE = "(e.g. 2h, 1h30m, or tap below)"
    DURATION_ERROR = "The duration you sent is not valid"
    DURATION_ERROR_EXAMPLE = "Please, try formats like 2h, 1d7:04, or 30m."
    HEADS_UP_QUESTION = "Heads-up before start?"
    SERVER_TIME_ASK = "Inform the server time shown in-game:"
    SERVER_TIME_EXAMPLE = "(e.g., 8-11-2025 17:09 or 17:09)"
    CUSTOM_TASK_ASK = "Inform the task name:"


@dataclass
class Messenger:
    """Telegram message sender with header and state management."""

    context: ContextTypes.DEFAULT_TYPE
    header: str = "⚔️ Last War Bot\n\n"
    parse_mode: ParseMode = ParseMode.MARKDOWN_V2
    with_header: bool = True

    def _get_msg_store(self) -> dict:
        """Get or create message store in user data."""
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
        """Save sent message metadata for later editing."""
        store = self._get_msg_store()
        store[store_key] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg,
        }

    def _get_chat_id(self, update: Update):
        """Extract chat ID from update."""
        chat = update.effective_chat
        return chat.id if chat else None

    def escape_md_v2(self, s: str) -> str:
        """Escape string for Markdown V2 format."""
        return escape_markdown(s, version=2)

    async def send(
        self,
        update: Update,
        msg: str,
        reply_markup: ReplyMarkup | None = None,
        store_key: str | None = None,
        store: bool = True,
    ):
        """Send a message with optional header and auto-store metadata."""
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
        """Reply to a message with optional header and auto-store metadata."""
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
        """Append a line to a stored message and remove its buttons."""
        try:
            store = self._get_msg_store()
            meta = store.get(store_key)
            if not meta:
                return
            chat_id = meta["chat_id"]
            message_id = meta["message_id"]
            base_text = meta["text"]
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
