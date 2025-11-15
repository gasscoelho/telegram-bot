import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.shared.webhook import WebhookNotifier

from .messages import Messages, get_random_reminder_message

logger = logging.getLogger(__name__)


class DuolingoBot:
    """Duolingo reminder bot handler."""

    def __init__(self, notifier: WebhookNotifier):
        self.notifier = notifier

    async def handle_duolingo_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /duolingo command - show main menu."""
        if not update.message:
            return
        keyboard = [
            [InlineKeyboardButton("Notify Friends", callback_data="duo:notify")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            Messages.DUOLINGO_WELCOME.value, reply_markup=reply_markup
        )

    async def _handle_notify_friends(self, query, context):
        """Handle notification request - send random message to webhook."""
        await query.edit_message_text(Messages.NOTIFYING_LOADING.value)
        reminder_message = get_random_reminder_message()
        ok = await self.notifier.post({"message": reminder_message})
        message = (
            Messages.NOTIFICATION_SUCCESS.value
            if ok
            else Messages.NOTIFICATION_FAILED.value
        )
        await context.bot.send_message(chat_id=query.message.chat.id, text=message)

    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        if not query or not query.message:
            return
        await query.answer()
        if query.data == "duo:notify":
            await self._handle_notify_friends(query, context)


def register(app: Application, webhook_url: str):
    """
    Register Duolingo bot handlers.

    Args:
        app: Telegram Application instance
        webhook_url: Webhook URL for sending notifications
    """
    bot = DuolingoBot(WebhookNotifier(webhook_url))
    app.add_handler(CommandHandler("duolingo", bot.handle_duolingo_command))
    app.add_handler(CallbackQueryHandler(bot.on_button, pattern=r"^duo:"))
