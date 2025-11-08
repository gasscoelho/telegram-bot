import logging
import random
from enum import Enum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .services import WebhookNotifier

logger = logging.getLogger(__name__)


class Messages(Enum):
    DUOLINGO_WELCOME = "🦉 Duolingo Bot\n\nWhat would you like to do?"
    NOTIFYING_LOADING = "⏳ Notifying your friends..."
    NOTIFICATION_SUCCESS = "🔔 Notification sent successfully!\n\nYour friends have been notified. Keep up the great work! 🎉"
    NOTIFICATION_FAILED = "❌ Failed to notify friends. Please try again later."


class ReminderService:
    @staticmethod
    def get_random_message() -> str:
        messages = [
            "Sobrevivi ao Duolingo de hoje! E você, já fez a sua lição ou vai deixar a coruja nervosa?",
            "A lição de hoje foi difícil, mas a ofensiva tá viva! 🧠🔥 Já garantiu a sua também?",
            "Duolingo feito com sucesso ✅ A coruja sorriu. E aí, vai deixar ela decepcionada hoje?",
            "Quase perdi a ofensiva, mas dei o gás no final! 🏃‍♂️🔥 Já fez a sua parte ou vai arriscar?",
            "🦉 Missão do dia cumprida! Agora é sua vez... Não me decepciona 😏",
            "Mais um dia de aprendizado, mais um dia salvo da fúria da coruja. 🕊️ E você, já estudou hoje?",
            "Se eu consegui fazer Duolingo hoje, você também consegue! 💪 Bora manter essa ofensiva viva!",
            "Já fiz minha parte no Duolingo. Agora é com vocês! 👀 Não vão quebrar a sequência hein!",
            "🧩 Duolingo do dia concluído! E você, já alimentou sua corujinha hoje?",
            "A lição de hoje quase me quebrou… mas a ofensiva tá salva 😮‍💨 Já garantiu a sua?",
        ]
        return random.choice(messages)


class DuolingoBot:
    def __init__(self, notifier: WebhookNotifier):
        self.notifier = notifier

    async def handle_duolingo_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        await query.edit_message_text(Messages.NOTIFYING_LOADING.value)
        reminder_message = ReminderService.get_random_message()
        ok = await self.notifier.post({"message": reminder_message})
        message = (
            Messages.NOTIFICATION_SUCCESS.value
            if ok
            else Messages.NOTIFICATION_FAILED.value
        )
        await context.bot.send_message(chat_id=query.message.chat.id, text=message)

    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query or not query.message:
            return
        await query.answer()
        if query.data == "duo:notify":
            await self._handle_notify_friends(query, context)


def register(app: Application, webhook_url: str):
    bot = DuolingoBot(WebhookNotifier(webhook_url))
    app.add_handler(CommandHandler("duolingo", bot.handle_duolingo_command))
    app.add_handler(CallbackQueryHandler(bot.on_button, pattern=r"^duo:"))
