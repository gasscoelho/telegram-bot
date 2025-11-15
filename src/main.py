import logging
from contextlib import asynccontextmanager
from http import HTTPStatus

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application

from src.bots.duolingo.handlers import register as register_duolingo
from src.bots.lastwar.handlers import register as register_lastwar
from src.config import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


ptb = (
    Application.builder()
    .updater(None)
    .token(config.BOT_TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

# Register bot handlers
register_duolingo(ptb, config.DUOLINGO_WEBHOOK_URL)
register_lastwar(ptb)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.setWebhook(config.TELEGRAM_WEBHOOK_URL)
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
        "src.main:app",
        host=config.FASTAPI_HOST,
        port=config.FASTAPI_PORT,
        reload=False,
    )
