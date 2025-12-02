from datetime import UTC, datetime, timedelta

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from src.bots.lastwar.models import Kind, ReminderRequest
from src.bots.lastwar.scheduler import (
    _build_job_id,
    _parse_job_id,
    cancel_job,
    cancel_user_jobs,
    format_job_display,
    format_task_label,
    get_scheduler,
    init_scheduler,
    list_user_jobs,
    schedule_reminder,
)

# Sample timestamp: 2024-01-15 12:00:00 UTC
SAMPLE_TS = int(datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC).timestamp())
TS_SUFFIX = str(SAMPLE_TS)[-3:]


@pytest.fixture
def scheduler():
    """Initialize and return a fresh scheduler for each test.

    Uses BackgroundScheduler for sync testing (works without event loop).
    """
    import src.bots.lastwar.scheduler as scheduler_module

    scheduler_module._scheduler = None
    sched = BackgroundScheduler(timezone=UTC)
    scheduler_module._scheduler = sched
    sched.start()
    yield sched
    sched.shutdown(wait=False)
    scheduler_module._scheduler = None


def test_build_job_id():
    job_id = _build_job_id(
        user_id=123,
        chat_id=456,
        kind="truck",
        timestamp=SAMPLE_TS,
        job_type="main",
    )
    assert job_id == f"lw:123:456:truck:{SAMPLE_TS}:main"


def test_parse_job_id_valid():
    parsed = _parse_job_id(f"lw:123:456:truck:{SAMPLE_TS}:main")
    assert parsed == {
        "prefix": "lw",
        "user_id": "123",
        "chat_id": "456",
        "kind": "truck",
        "timestamp": str(SAMPLE_TS),
        "type": "main",
    }


def test_parse_job_id_invalid_prefix():
    assert _parse_job_id("xx:123:456:truck:1234567890:main") is None


def test_parse_job_id_wrong_parts_count():
    assert _parse_job_id("lw:123:456:truck:main") is None
    assert _parse_job_id("lw:123:456:truck:1234567890:main:extra") is None


def test_parse_job_id_empty():
    assert _parse_job_id("") is None


def test_get_scheduler_without_init_raises():
    import src.bots.lastwar.scheduler as scheduler_module

    scheduler_module._scheduler = None
    with pytest.raises(RuntimeError, match="Scheduler not initialized"):
        get_scheduler()


def test_init_scheduler_returns_scheduler(scheduler):
    assert scheduler is not None
    assert get_scheduler() is scheduler


def test_init_scheduler_idempotent(scheduler):
    """Calling init_scheduler multiple times returns the same instance."""
    second = init_scheduler()
    assert second is scheduler


def test_format_task_label_truck():
    label = format_task_label(Kind.TRUCK, None, SAMPLE_TS)
    assert label == f"Truck #{TS_SUFFIX}"


def test_format_task_label_build():
    label = format_task_label(Kind.BUILD, None, SAMPLE_TS)
    assert label == f"Build #{TS_SUFFIX}"


def test_format_task_label_custom_uses_task_name():
    label = format_task_label(Kind.CUSTOM, "My Task", SAMPLE_TS)
    assert label == f"My Task #{TS_SUFFIX}"


def test_format_task_label_custom_without_name_uses_kind():
    label = format_task_label(Kind.CUSTOM, None, SAMPLE_TS)
    assert label == f"Custom #{TS_SUFFIX}"


def test_schedule_reminder_main_only(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time=None,
    )

    job_ids, task_label = schedule_reminder(request)

    assert len(job_ids) == 1
    assert "main" in job_ids[0]
    assert "Truck" in task_label

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job_ids[0]


def test_schedule_reminder_with_headsup(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.BUILD,
        task_name=None,
        duration=timedelta(hours=2),
        lead_time="10m",
    )

    job_ids, task_label = schedule_reminder(request)

    assert len(job_ids) == 2
    assert any("main" in jid for jid in job_ids)
    assert any("headsup" in jid for jid in job_ids)
    assert "Build" in task_label

    jobs = scheduler.get_jobs()
    assert len(jobs) == 2


def test_schedule_reminder_headsup_skipped_when_longer_than_duration(scheduler):
    """Heads-up should be skipped if lead_time >= duration."""
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(minutes=5),
        lead_time="10m",
    )

    job_ids, _ = schedule_reminder(request)

    assert len(job_ids) == 1
    assert "main" in job_ids[0]


def test_schedule_reminder_custom_task(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.CUSTOM,
        task_name="Farm Resources",
        duration=timedelta(minutes=30),
        lead_time=None,
    )

    job_ids, task_label = schedule_reminder(request)

    assert len(job_ids) == 1
    assert "Farm Resources" in task_label


def test_format_job_display_main():
    job_id = f"lw:123:456:truck:{SAMPLE_TS}:main"
    next_run = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    display = format_job_display(job_id, next_run)

    assert f"Truck #{TS_SUFFIX}" in display
    assert "(heads-up)" not in display


def test_format_job_display_headsup():
    job_id = f"lw:123:456:build:{SAMPLE_TS}:headsup"
    next_run = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    display = format_job_display(job_id, next_run)

    assert f"Build #{TS_SUFFIX}" in display
    assert "(heads-up)" in display


def test_format_job_display_invalid_job_id():
    job_id = "invalid:job:id"
    next_run = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    display = format_job_display(job_id, next_run)

    assert "Unknown" in display


def test_format_job_display_unknown_kind():
    job_id = f"lw:123:456:unknownkind:{SAMPLE_TS}:main"
    next_run = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    display = format_job_display(job_id, next_run)

    assert "Unknown" in display


def test_list_user_jobs_empty(scheduler):
    jobs = list_user_jobs(user_id=123, chat_id=456)
    assert jobs == []


def test_list_user_jobs_returns_matching_jobs(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time="5m",
    )
    schedule_reminder(request)

    jobs = list_user_jobs(user_id=123, chat_id=456)

    assert len(jobs) == 2  # main + headsup


def test_list_user_jobs_filters_by_user_and_chat(scheduler):
    request1 = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time=None,
    )
    schedule_reminder(request1)

    request2 = ReminderRequest(
        user_id=999,
        chat_id=456,
        kind=Kind.BUILD,
        task_name=None,
        duration=timedelta(hours=2),
        lead_time=None,
    )
    schedule_reminder(request2)

    jobs = list_user_jobs(user_id=123, chat_id=456)
    assert len(jobs) == 1
    assert "123" in jobs[0]["id"]


def test_list_user_jobs_sorted_by_time(scheduler):
    request1 = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=2),
        lead_time=None,
    )
    schedule_reminder(request1)

    request2 = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.BUILD,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time=None,
    )
    schedule_reminder(request2)

    jobs = list_user_jobs(user_id=123, chat_id=456)

    assert len(jobs) == 2
    assert jobs[0]["next_run_time"] < jobs[1]["next_run_time"]


def test_cancel_job_success(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time=None,
    )
    job_ids, _ = schedule_reminder(request)

    result = cancel_job(job_ids[0])

    assert result is True
    assert len(scheduler.get_jobs()) == 0


def test_cancel_job_not_found(scheduler):
    result = cancel_job("nonexistent:job:id")
    assert result is False


def test_cancel_user_jobs_all(scheduler):
    request = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time="5m",
    )
    schedule_reminder(request)

    count = cancel_user_jobs(user_id=123, chat_id=456)

    assert count == 2  # main + headsup
    assert len(scheduler.get_jobs()) == 0


def test_cancel_user_jobs_none_to_cancel(scheduler):
    count = cancel_user_jobs(user_id=123, chat_id=456)
    assert count == 0


def test_cancel_user_jobs_only_cancels_matching(scheduler):
    request1 = ReminderRequest(
        user_id=123,
        chat_id=456,
        kind=Kind.TRUCK,
        task_name=None,
        duration=timedelta(hours=1),
        lead_time=None,
    )
    schedule_reminder(request1)

    request2 = ReminderRequest(
        user_id=999,
        chat_id=456,
        kind=Kind.BUILD,
        task_name=None,
        duration=timedelta(hours=2),
        lead_time=None,
    )
    schedule_reminder(request2)

    count = cancel_user_jobs(user_id=123, chat_id=456)

    assert count == 1
    remaining_jobs = scheduler.get_jobs()
    assert len(remaining_jobs) == 1
    assert "999" in remaining_jobs[0].id
