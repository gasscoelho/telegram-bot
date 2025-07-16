import logging
import os
import random
from contextlib import asynccontextmanager
from enum import Enum
from http import HTTPStatus

import aiohttp
import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


class ReminderService:
    @staticmethod
    def get_random_reminder():
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


class Config:
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")


class Messages(Enum):
    DUOLINGO_WELCOME = "🦉 Duolingo Bot\n\nWhat would you like to do?"
    NOTIFYING_LOADING = "⏳ Notifying your friends..."
    NOTIFICATION_SUCCESS = "🔔 Notification sent successfully!\n\nYour friends have been notified. Keep up the great work! 🎉"
    NOTIFICATION_FAILED = "❌ Failed to notify friends. Please try again later."


class WebhookService:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def notify_friends(self, reminder_message: str) -> bool:
        try:
            payload = {"message": reminder_message}
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Webhook request failed: {e}")
            return False


class DuolingoBot:
    def __init__(self, webhook_service: WebhookService):
        self.webhook_service = webhook_service

    async def handle_duolingo_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        keyboard = [
            [InlineKeyboardButton("Notify Friends", callback_data="notify_friends")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if not update.message:
            return
        await update.message.reply_text(
            Messages.DUOLINGO_WELCOME.value, reply_markup=reply_markup
        )

    async def handle_button_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        if not query or not query.message:
            return
        await query.answer()
        if query.data == "notify_friends":
            await self._handle_notify_friends(query, context)

    async def _handle_notify_friends(self, query, context):
        await query.edit_message_text(Messages.NOTIFYING_LOADING.value)
        reminder_message = ReminderService.get_random_reminder()
        success = await self.webhook_service.notify_friends(reminder_message)
        message = (
            Messages.NOTIFICATION_SUCCESS.value
            if success
            else Messages.NOTIFICATION_FAILED.value
        )
        await context.bot.send_message(chat_id=query.message.chat.id, text=message)


# Initialize bot application
webhook_service = WebhookService(Config.N8N_WEBHOOK_URL)
duolingo_bot = DuolingoBot(webhook_service)
ptb = (
    Application.builder()
    .updater(None)
    .token(Config.BOT_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

# Add bot handlers
ptb.add_handler(CommandHandler("duolingo", duolingo_bot.handle_duolingo_command))
ptb.add_handler(CallbackQueryHandler(duolingo_bot.handle_button_callback))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.setWebhook(Config.TELEGRAM_WEBHOOK_URL)
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)


if __name__ == "__main__":
    logger.info("Starting Duolingo Bot with FastAPI...")
    uvicorn.run(
        "main:app",
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        reload=False,
    )
