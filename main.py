import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application

from bot.duolingo import register as register_duolingo
from bot.lastwar import register as register_lastwar

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

load_dotenv()


class Config:
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")

    # Feature-specific outbound webhooks:
    DUOLINGO_WEBHOOK_URL = os.getenv("DUOLINGO_WEBHOOK_URL", "")
    LASTWAR_WEBHOOK_URL = os.getenv("LASTWAR_WEBHOOK_URL", "")


ptb = (
    Application.builder()
    .updater(None)
    .token(Config.BOT_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

# Register bot handlers
register_duolingo(ptb, Config.DUOLINGO_WEBHOOK_URL)
register_lastwar(ptb)


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
    logger.info("Starting Bots with FastAPI...")
    uvicorn.run(
        "main:app",
        host=Config.FASTAPI_HOST,
        port=Config.FASTAPI_PORT,
        reload=False,
    )
