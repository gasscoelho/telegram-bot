from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message
from telegram.ext import ConversationHandler

from src.bots.lastwar import handlers
from src.bots.lastwar.conversation import states
from src.bots.lastwar.messages import Messages
from src.bots.lastwar.models import Kind, ReminderRequest, get_user_context
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

    # Enter server time "17:09" - should calculate duration until that time
    # NOT be treated as 17h 9m duration
    # Mock datetime.now() to return a fixed time (14:00)
    mock_now = datetime(2025, 12, 3, 14, 0, 0, tzinfo=UTC)
    with patch("src.shared.utils.duration.datetime") as mock_datetime:
        # Mock now() to return mock_now, and astimezone() returns itself
        mock_now_obj = MagicMock()
        mock_now_obj.astimezone.return_value = mock_now
        mock_datetime.now.return_value = mock_now_obj
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        update = make_message_update(
            "17:09", user=user, chat=chat, bot=fake_context.bot
        )
        fake_context.bot.send_message = AsyncMock()
        next_state = await handlers.on_enter_duration(update, fake_context)
        assert next_state == states.ENTERING_HEADS_UP

    # Server time "17:09" with now=14:00 should be ~3h 9m, NOT 17h 9m
    assert user_ctx.value == timedelta(hours=3, minutes=9), (
        f"Server time '17:09' with now=14:00 should be 3h 9m. Got {user_ctx.value}."
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
async def test_full_flow_truck_with_text_input(
    mock_answer, mock_scheduler, fake_context, user, chat
):
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

    # Verify schedule_reminder was called with correct ReminderRequest
    mock_scheduler.assert_called_once()
    call_args = mock_scheduler.call_args
    request: ReminderRequest = call_args.args[0]

    assert request.user_id == user.id, "Should schedule reminder for correct user"
    assert request.chat_id == chat.id, "Should schedule reminder for correct chat"
    assert request.kind == Kind.TRUCK, "Should schedule reminder with correct task kind"
    assert request.duration == timedelta(minutes=45), (
        "Should schedule reminder with correct duration"
    )
    assert request.lead_time == "3m", (
        "Should schedule reminder with correct heads-up time"
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


@pytest.mark.asyncio
async def test_natural_language_ministry_with_server_time(fake_context, user, chat):
    """Test NL ministry input with server_time is converted to duration correctly."""
    mock_now = datetime(2025, 12, 3, 14, 0, 0, tzinfo=UTC)

    with (
        patch("src.bots.lastwar.handlers.interpret_natural_command") as mock_interpret,
        patch("src.shared.utils.duration.datetime") as mock_datetime,
    ):
        # Mock now() to return mock_now, and astimezone() returns itself
        mock_now_obj = MagicMock()
        mock_now_obj.astimezone.return_value = mock_now
        mock_datetime.now.return_value = mock_now_obj
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Simulate LLM returning server_time for ministry
        mock_interpret.return_value = ParsedCommand(
            kind=Kind.MINISTRY,
            task_name="ministry promotion",
            server_time="17:09",
            language="en",
        )
        update = make_message_update(
            "I'll be promoted at 17:09",
            user=user,
            chat=chat,
            bot=fake_context.bot,
        )
        fake_context.bot.send_message = AsyncMock()
        next_state = await handlers.on_natural_command(update, fake_context)

        assert next_state == states.ENTERING_HEADS_UP
        user_ctx = get_user_context(fake_context)
        assert user_ctx.kind == Kind.MINISTRY
        # 17:09 - 14:00 = 3h 9m
        assert user_ctx.value == timedelta(hours=3, minutes=9), (
            f"server_time '17:09' with now=14:00 should be 3h 9m. Got {user_ctx.value}"
        )


@pytest.mark.asyncio
async def test_natural_language_ministry_tomorrow(fake_context, user, chat):
    """Test NL ministry with 'tomorrow' adds extra day to duration."""
    mock_now = datetime(2025, 12, 3, 14, 0, 0, tzinfo=UTC)

    with (
        patch("src.bots.lastwar.handlers.interpret_natural_command") as mock_interpret,
        patch("src.shared.utils.duration.datetime") as mock_datetime,
    ):
        # Mock now() to return mock_now, and astimezone() returns itself
        mock_now_obj = MagicMock()
        mock_now_obj.astimezone.return_value = mock_now
        mock_datetime.now.return_value = mock_now_obj
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # LLM sets days=1 for "tomorrow"
        mock_interpret.return_value = ParsedCommand(
            kind=Kind.MINISTRY,
            task_name="ministry promotion",
            server_time="10:00",
            days=1,
            language="en",
        )
        update = make_message_update(
            "promoted tomorrow at 10:00",
            user=user,
            chat=chat,
            bot=fake_context.bot,
        )
        fake_context.bot.send_message = AsyncMock()
        next_state = await handlers.on_natural_command(update, fake_context)

        assert next_state == states.ENTERING_HEADS_UP
        user_ctx = get_user_context(fake_context)
        # 10:00 is before 14:00, so parse_server_time_to_duration wraps to tomorrow (20h)
        # Then we add days=1, so total = 20h + 24h = 44h = 1d 20h
        assert user_ctx.value == timedelta(days=1, hours=20), (
            f"'tomorrow at 10:00' with now=14:00 should be 1d 20h. Got {user_ctx.value}"
        )


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_list_with_no_reminders(mock_answer, fake_context, user, chat):
    """Test 'list' option when there are no active reminders."""
    with patch("src.bots.lastwar.handlers.list_user_jobs") as mock_list:
        mock_list.return_value = []
        update = make_callback_query_update(
            "lw:list", user=user, chat=chat, message_text=Messages.WELCOME.value
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_choose(update, fake_context)

        assert next_state == ConversationHandler.END
        mock_list.assert_called_once_with(user.id, chat.id)
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "No active reminders" in kwargs["text"]


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_list_with_reminders(mock_answer, fake_context, user, chat):
    """Test 'list' option displays active reminders."""

    with (
        patch("src.bots.lastwar.handlers.list_user_jobs") as mock_list,
        patch("src.bots.lastwar.handlers.format_job_display") as mock_format,
    ):
        mock_list.return_value = [
            {
                "id": "lw:123:456:truck:1234567890:main",
                "next_run_time": datetime.now(UTC),
            },
            {
                "id": "lw:123:456:truck:1234567890:headsup",
                "next_run_time": datetime.now(UTC),
            },
        ]
        mock_format.side_effect = [
            "Truck #890 - Mon 14:30",
            "Truck #890 (heads-up) - Mon 14:25",
        ]

        update = make_callback_query_update(
            "lw:list", user=user, chat=chat, message_text=Messages.WELCOME.value
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_choose(update, fake_context)

        assert next_state == ConversationHandler.END
        mock_list.assert_called_once_with(user.id, chat.id)
        assert mock_format.call_count == 2
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "Active Reminders" in kwargs["text"]


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_unschedule_with_no_reminders(
    mock_answer, fake_context, user, chat
):
    """Test 'unschedule' option when there are no reminders."""
    with patch("src.bots.lastwar.handlers.list_user_jobs") as mock_list:
        mock_list.return_value = []
        update = make_callback_query_update(
            "lw:unschedule", user=user, chat=chat, message_text=Messages.WELCOME.value
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_choose(update, fake_context)

        assert next_state == ConversationHandler.END
        mock_list.assert_called_once_with(user.id, chat.id)
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "No reminders to unschedule" in kwargs["text"]


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_choose_unschedule_shows_menu(mock_answer, fake_context, user, chat):
    """Test 'unschedule' option shows menu with reminders."""
    mock_jobs = [
        {"id": "lw:42:123:truck:main:1234567890", "next_run_time": datetime.now(UTC)},
        {"id": "lw:42:123:build:main:1234567891", "next_run_time": datetime.now(UTC)},
    ]
    with patch("src.bots.lastwar.handlers.list_user_jobs") as mock_list:
        mock_list.return_value = mock_jobs
        update = make_callback_query_update(
            "lw:unschedule", user=user, chat=chat, message_text=Messages.WELCOME.value
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_choose(update, fake_context)

        assert next_state == states.SELECTING_UNSCHEDULE
        # Jobs should be stored for later reference
        assert fake_context.user_data.get("lw_unschedule_jobs") == mock_jobs
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "Select reminder to unschedule" in kwargs["text"]
        # Should have inline keyboard with options
        assert kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_select_unschedule_all(mock_answer, fake_context, user, chat):
    """Test selecting 'Unschedule All' cancels all reminders."""
    with patch("src.bots.lastwar.handlers.cancel_user_jobs") as mock_cancel:
        mock_cancel.return_value = 3
        update = make_callback_query_update(
            "lw:unsched:all", user=user, chat=chat, message_text="Select reminder"
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_select_unschedule(update, fake_context)

        assert next_state == ConversationHandler.END
        mock_cancel.assert_called_once_with(user.id, chat.id)
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "Unscheduled 3 reminders" in kwargs["text"]


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_select_unschedule_single(mock_answer, fake_context, user, chat):
    """Test selecting a single reminder to unschedule."""
    job_id = "lw:42:123:truck:main:1234567890"
    mock_jobs = [
        {"id": job_id, "next_run_time": datetime.now(UTC)},
    ]
    fake_context.user_data["lw_unschedule_jobs"] = mock_jobs

    with patch("src.bots.lastwar.handlers.cancel_job") as mock_cancel:
        mock_cancel.return_value = True
        update = make_callback_query_update(
            "lw:unsched:1", user=user, chat=chat, message_text="Select reminder"
        )
        fake_context.bot.send_message = AsyncMock()

        next_state = await handlers.on_select_unschedule(update, fake_context)

        assert next_state == ConversationHandler.END
        mock_cancel.assert_called_once_with(job_id)
        fake_context.bot.send_message.assert_called()
        _, kwargs = fake_context.bot.send_message.call_args
        assert "Unscheduled" in kwargs["text"]


@pytest.mark.asyncio
@patch.object(CallbackQuery, "answer", new_callable=AsyncMock)
async def test_on_select_unschedule_exit(mock_answer, fake_context, user, chat):
    """Test selecting 'Exit' returns to end without unscheduling."""
    fake_context.user_data["lw_unschedule_jobs"] = [{"id": "test", "next_run_time": None}]

    update = make_callback_query_update(
        "lw:unsched:exit", user=user, chat=chat, message_text="Select reminder"
    )
    fake_context.bot.send_message = AsyncMock()

    next_state = await handlers.on_select_unschedule(update, fake_context)

    assert next_state == ConversationHandler.END
    # Jobs should be cleared from context
    assert fake_context.user_data.get("lw_unschedule_jobs") is None
