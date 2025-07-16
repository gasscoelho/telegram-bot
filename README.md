### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

1. **Create virtual environment**
```bash
uv venv .venv --python=$(which python3.13)
source .venv/bin/activate
```

2. **Install dependencies**
```bash
# Production dependencies
uv sync

# Development dependencies
uv sync --group dev
```

3. **Configure environment variables**

### Running the Bot

```bash
# Terminal 1: Start ngrok (Development Only)
ngrok http 8000

# Terminal 2: Update webhook URL and run bot
export TELEGRAM_WEBHOOK_URL="https://your-ngrok-url.ngrok.io/webhook"
python main.py
```
