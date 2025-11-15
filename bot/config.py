from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # Server
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000

    # Bot
    BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""

    # Feature-specific outbound webhooks
    DUOLINGO_WEBHOOK_URL: str = ""
    LASTWAR_WEBHOOK_URL: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


config = Config()
