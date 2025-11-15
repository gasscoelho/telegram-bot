### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

**1. Create virtual environment**
```bash
uv venv .venv --python=$(which python3.13)
source .venv/bin/activate
```

**2. Install dependencies**
```bash
# Production dependencies
uv sync

# Development dependencies
uv sync --group dev
```

**3. Configure environment variables**

Copy the example file:

```bash
cp .env.example .env
```

Then edit `.env` with the bot credentials and webhook URLs.

### Running the Bot

```bash
# Terminal 1: Start ngrok (Development Only)
ngrok http 8000

# Terminal 2: Run the bot
python main.py
```
