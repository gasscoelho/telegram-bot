from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Bot, CallbackQuery, Chat, Message, Update, User


@pytest.fixture
def bot():
    """Create a mock bot instance."""
    return MagicMock(spec=Bot)


@pytest.fixture
def user():
    """Create a test user."""
    return User(id=42, first_name="Test", is_bot=False)


@pytest.fixture
def chat():
    """Create a test chat."""
    return Chat(id=123, type="private")


@pytest.fixture
def fake_context(bot):
    """Create a fake context that matches ContextTypes.DEFAULT_TYPE."""
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()

    context = SimpleNamespace(
        bot=bot,
        user_data={},
        bot_data={},
        chat_data={},
    )
    return context


def make_message_update(
    text: str,
    user: User | None = None,
    chat: Chat | None = None,
    message_id: int = 1,
    bot: Bot | None = None,
) -> Update:
    """
    Create a message update for testing.

    Args:
        text: Message text
        user: User object (creates default if None)
        chat: Chat object (creates default if None)
        message_id: Message ID
        bot: Bot object to set on message (optional)

    Returns:
        Update object with message
    """
    if user is None:
        user = User(id=42, first_name="Test", is_bot=False)
    if chat is None:
        chat = Chat(id=123, type="private")

    message = Message(
        message_id=message_id,
        date=datetime.now(tz=UTC),
        chat=chat,
        from_user=user,
        text=text,
    )

    if bot is not None:
        message.set_bot(bot)

    return Update(update_id=message_id, message=message)


def make_callback_query_update(
    data: str,
    user: User | None = None,
    chat: Chat | None = None,
    message_id: int = 1,
    message_text: str = "Test message",
    bot: Bot | None = None,
) -> Update:
    """
    Create a callback query update for testing.

    Note:
        The callback_query.answer method needs to be mocked in tests using monkeypatch
        or unittest.mock.patch before calling handlers.
    """
    if user is None:
        user = User(id=42, first_name="Test", is_bot=False)
    if chat is None:
        chat = Chat(id=123, type="private")
    if bot is None:
        bot = MagicMock(spec=Bot)

    message = Message(
        message_id=message_id,
        date=datetime.now(tz=UTC),
        chat=chat,
        from_user=user,
        text=message_text,
    )
    message.set_bot(bot)

    callback_query = CallbackQuery(
        id=f"cbq_{message_id}",
        from_user=user,
        chat_instance=str(chat.id),
        message=message,
        data=data,
    )
    callback_query.set_bot(bot)

    return Update(update_id=message_id, callback_query=callback_query)
