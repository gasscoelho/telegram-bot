from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from telegram import CallbackQuery, Message
from telegram.ext import ConversationHandler

from src.bots.lastwar import handlers
from src.bots.lastwar.conversation import states
from src.bots.lastwar.messages import Messages
from src.bots.lastwar.models import Kind, get_user_context
from src.bots.lastwar.nl.interpreter import ParsedCommand
from tests.conftest import make_callback_query_update, make_message_update


@pytest.mark.asyncio
async def test_on_start_shows_menu(fake_context, user, chat):
    """Test that /lw command shows the task selection menu."""
    update = make_message_update("/lw", user=user, chat=chat, bot=fake_context.bot)
    next_state = await handlers.on_start(update, fake_context)
    assert next_state == states.CHOOSING, "Should transition to CHOOSING state"
    fake_context.bot.send_message.assert_called_once()
    _, kwargs = fake_context.bot.send_message.call_args
    assert Messages.WELCOME.value in kwargs["text"], (
        "Welcome message should be in response"
    )
    reply_markup = kwargs["reply_markup"]
    assert reply_markup is not None, "Should include keyboard markup"
    keyboard = reply_markup.inline_keyboard
    assert len(keyboard) > 0, "Keyboard should have task selection buttons"
    msgs = fake_context.user_data.get("lw_msgs")
    assert msgs is not None, "Should store message metadata in user_data"
    assert "menu" in msgs, "Should store menu message for later editing"


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_truck_transitions_to_duration(
    mock_answer, fake_context, user, chat
):
    """Test selecting 'truck' task transitions to duration entry."""
    update = make_callback_query_update(
        "lw:truck", user=user, chat=chat, message_text=Messages.WELCOME.value
    )
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_choose(update, fake_context)
    assert next_state == states.ENTERING_DURATION, (
        "Should transition to duration entry state"
    )
    user_ctx = get_user_context(fake_context)
    assert user_ctx.kind == Kind.TRUCK, "Should set task kind to TRUCK in context"
    fake_context.bot.send_message.assert_called_once()
    _, kwargs = fake_context.bot.send_message.call_args
    assert Messages.DURATION_QUESTION.value in kwargs["text"], "Should ask for duration"


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_custom_transitions_to_custom_task(
    mock_answer, fake_context, user, chat
):
    """Test selecting 'custom' task transitions to custom task name entry."""
    update = make_callback_query_update(
        "lw:custom", user=user, chat=chat, message_text=Messages.WELCOME.value
    )
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_choose(update, fake_context)
    assert next_state == states.ENTERING_CUSTOM_TASK, (
        "Should transition to custom task name entry"
    )
    user_ctx = get_user_context(fake_context)
    assert user_ctx.kind == Kind.CUSTOM, "Should set task kind to CUSTOM in context"
    fake_context.bot.send_message.assert_called_once()
    _, kwargs = fake_context.bot.send_message.call_args
    assert Messages.CUSTOM_TASK_ASK.value in kwargs["text"], (
        "Should ask for custom task name"
    )


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_ministry_transitions_to_server_time(
    mock_answer, fake_context, user, chat
):
    """Test selecting 'ministry' task transitions to server time entry."""
    update = make_callback_query_update(
        "lw:ministry", user=user, chat=chat, message_text=Messages.WELCOME.value
    )
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_choose(update, fake_context)
    assert next_state == states.ENTERING_DURATION, (
        "Should transition to duration/server time entry"
    )
    user_ctx = get_user_context(fake_context)
    assert user_ctx.kind == Kind.MINISTRY, "Should set task kind to MINISTRY in context"
    fake_context.bot.send_message.assert_called_once()
    _, kwargs = fake_context.bot.send_message.call_args
    assert "server time" in kwargs["text"].lower(), (
        "Should ask for server time (text may be Markdown escaped)"
    )


@pytest.mark.asyncio
async def test_on_enter_custom_task_stores_name(fake_context, user, chat):
    """Test entering a custom task name stores it in context."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.CUSTOM
    update = make_message_update(
        "Farm resources", user=user, chat=chat, bot=fake_context.bot
    )
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_custom_task(update, fake_context)
    assert next_state == states.ENTERING_DURATION, (
        "Should transition to duration entry after getting custom task name"
    )
    assert user_ctx.task_name == "Farm resources", (
        "Should store custom task name in context"
    )


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_enter_duration_with_button(mock_answer, fake_context, user, chat):
    """Test selecting duration from button works correctly."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.TRUCK
    update = make_callback_query_update("lw:dur:2h", user=user, chat=chat)
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_duration(update, fake_context)
    assert next_state == states.ENTERING_HEADS_UP, (
        "Should transition to heads-up selection after duration"
    )
    assert user_ctx.value == timedelta(hours=2), (
        "Should parse and store 2h duration from button"
    )


@pytest.mark.asyncio
async def test_on_enter_duration_with_text(fake_context, user, chat):
    """Test entering duration as text works correctly."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.BUILD
    update = make_message_update("1h30m", user=user, chat=chat, bot=fake_context.bot)
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_duration(update, fake_context)
    assert next_state == states.ENTERING_HEADS_UP, (
        "Should transition to heads-up selection after text duration"
    )
    assert user_ctx.value == timedelta(hours=1, minutes=30), (
        "Should parse and store '1h30m' text duration correctly"
    )


@pytest.mark.asyncio
async def test_on_enter_duration_invalid_format(fake_context, user, chat):
    """Test invalid duration format shows error and stays in same state."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.TRUCK
    update = make_message_update(
        "invalid duration", user=user, chat=chat, bot=fake_context.bot
    )
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_duration(update, fake_context)
    assert next_state == states.ENTERING_DURATION, (
        "Should stay in duration entry state on invalid input"
    )
    fake_context.bot.send_message.assert_called_once()
    _, kwargs = fake_context.bot.send_message.call_args
    assert Messages.DURATION_ERROR.value in kwargs["text"], (
        "Should send error message for invalid duration format"
    )


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_enter_heads_up_with_button(mock_answer, fake_context, user, chat):
    """Test selecting heads-up time from button completes flow."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.TRUCK
    user_ctx.value = timedelta(hours=2)
    update = make_callback_query_update("lw:lead_time:5m", user=user, chat=chat)
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_heads_up(update, fake_context)
    assert next_state == ConversationHandler.END, (
        "Should complete conversation after heads-up selection"
    )
    assert user_ctx.lead_time == "5m", "Should store selected lead time in context"
    fake_context.bot.send_message.assert_called()
    _, kwargs = fake_context.bot.send_message.call_args
    assert "Scheduled" in kwargs["text"], (
        "Should send completion summary with task details"
    )
    assert "Truck" in kwargs["text"], "Summary should include task type"
    assert "2h" in kwargs["text"], "Summary should include duration"


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_enter_heads_up_skip(mock_answer, fake_context, user, chat):
    """Test skipping heads-up completes flow."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.BUILD
    user_ctx.value = timedelta(hours=1, minutes=30)
    update = make_callback_query_update("lw:lead_time:skip", user=user, chat=chat)
    fake_context.bot.send_message = AsyncMock()
    next_state = await handlers.on_enter_heads_up(update, fake_context)
    assert next_state == ConversationHandler.END, (
        "Should complete conversation when skipping heads-up"
    )
    assert user_ctx.lead_time is None, "Should have no lead time when skipped"
    fake_context.bot.send_message.assert_called()
    _, kwargs = fake_context.bot.send_message.call_args
    assert "Scheduled" in kwargs["text"], "Should send completion summary"


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_full_flow_truck_with_text_input(mock_answer, fake_context, user, chat):
    """Test complete flow: start -> truck -> duration text -> heads-up -> complete."""
    # Step 1: Start
    update = make_message_update("/lw", user=user, chat=chat, bot=fake_context.bot)
    state = await handlers.on_start(update, fake_context)
    assert state == states.CHOOSING

    # Step 2: Choose truck
    update = make_callback_query_update("lw:truck", user=user, chat=chat)
    fake_context.bot.send_message = AsyncMock()
    state = await handlers.on_choose(update, fake_context)
    assert state == states.ENTERING_DURATION

    # Step 3: Enter duration as text
    update = make_message_update("45m", user=user, chat=chat, bot=fake_context.bot)
    fake_context.bot.send_message = AsyncMock()
    state = await handlers.on_enter_duration(update, fake_context)
    assert state == states.ENTERING_HEADS_UP

    # Step 4: Select heads-up
    update = make_callback_query_update("lw:lead_time:3m", user=user, chat=chat)
    fake_context.bot.send_message = AsyncMock()

    # Store context before it's cleared
    user_ctx_before = get_user_context(fake_context)
    kind_before = user_ctx_before.kind
    value_before = user_ctx_before.value

    state = await handlers.on_enter_heads_up(update, fake_context)
    assert state == ConversationHandler.END, (
        "Should complete conversation after full flow"
    )
    assert kind_before == Kind.TRUCK, "Kind should have been set to TRUCK during flow"
    assert value_before == timedelta(minutes=45), (
        "Duration should have been parsed as 45 minutes"
    )
    assert "lw_ctx" not in fake_context.user_data, (
        "Context should be cleared after completion"
    )


@pytest.mark.asyncio
@patch.object(Message, "reply_text", new_callable=AsyncMock)
async def test_on_cancel_clears_context(mock_reply, fake_context, user, chat):
    """Test /cancel command clears user context."""
    user_ctx = get_user_context(fake_context)
    user_ctx.kind = Kind.TRUCK
    user_ctx.value = timedelta(hours=1)
    fake_context.user_data["lw_msgs"] = {"test": "data"}
    update = make_message_update("/cancel", user=user, chat=chat)
    next_state = await handlers.on_cancel(update, fake_context)
    assert next_state == ConversationHandler.END, (
        "Should end conversation when cancelled"
    )
    assert "lw_ctx" not in fake_context.user_data, (
        "Should clear conversation context on cancel"
    )
    assert "lw_msgs" not in fake_context.user_data, (
        "Should clear message metadata on cancel"
    )


@pytest.mark.asyncio
async def test_natural_language_command(fake_context, user, chat):
    """Test natural language input is processed correctly."""
    with patch("src.bots.lastwar.handlers.interpret_natural_command") as mock_interpret:
        mock_interpret.return_value = ParsedCommand(
            kind=Kind.TRUCK,
            task_name="truck arrival",
            hours=2,
            minutes=30,
            language="en",
        )
        update = make_message_update(
            "remind me about truck in 2h30m", user=user, chat=chat, bot=fake_context.bot
        )
        fake_context.bot.send_message = AsyncMock()
        next_state = await handlers.on_natural_command(update, fake_context)
        assert next_state == states.ENTERING_HEADS_UP, (
            "Should skip to ENTERING_HEADS_UP after parsing natural language"
        )
        user_ctx = get_user_context(fake_context)
        assert user_ctx.kind == Kind.TRUCK, (
            "Should extract kind from natural language input"
        )
        assert user_ctx.task_name == "truck arrival", (
            "Should extract task name from natural language input"
        )
        assert user_ctx.value == timedelta(hours=2, minutes=30), (
            "Should extract and parse duration from natural language input"
        )
