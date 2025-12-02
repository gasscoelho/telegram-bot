"""APScheduler integration for Last War reminders."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.shared.utils.duration import as_apscheduler_date_args, format_duration

from .models import Kind, ReminderRequest

logger = logging.getLogger(__name__)

# Private global scheduler instance
_scheduler: AsyncIOScheduler | None = None

# Job ID format constants
_JOB_ID_PREFIX = "lw"
_JOB_ID_SEPARATOR = ":"


def _build_job_id(
    user_id: int, chat_id: int, kind: str, timestamp: int, job_type: str
) -> str:
    return f"{_JOB_ID_PREFIX}:{user_id}:{chat_id}:{kind}:{timestamp}:{job_type}"


def _parse_job_id(job_id: str) -> dict[str, str] | None:
    """
    Parse a job ID into its components.
    """
    parts = job_id.split(_JOB_ID_SEPARATOR)
    if len(parts) != 6 or parts[0] != _JOB_ID_PREFIX:
        return None
    return {
        "prefix": parts[0],
        "user_id": parts[1],
        "chat_id": parts[2],
        "kind": parts[3],
        "timestamp": parts[4],
        "type": parts[5],
    }


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and return the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=UTC)
    return _scheduler


def get_scheduler() -> AsyncIOScheduler:
    """Get the scheduler instance (must be initialized first)."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    return _scheduler


async def send_reminder(
    chat_id: int,
    message: str,
    webhook_url: str | None = None,
) -> None:
    """
    Send a reminder notification (mocked for now).

    Args:
        chat_id: Telegram chat ID to send message to
        message: Message content to send
        webhook_url: Optional webhook URL for n8n integration

    TODO: Implement actual webhook notification to n8n
    """
    logger.info(f"[MOCK REMINDER] chat_id={chat_id}, message={message}")
    # Future implementation:
    # if webhook_url:
    #     await WebhookNotifier(webhook_url).post({
    #         "chat_id": chat_id,
    #         "message": message,
    #     })


def format_task_label(kind: Kind, task_name: str | None, timestamp: int) -> str:
    """
    Format a task label with timestamp suffix.

    Args:
        kind: Task kind
        task_name: Custom task name (for Kind.CUSTOM)
        timestamp: Unix timestamp for unique identifier

    Returns:
        Formatted task label (e.g., "Truck #456")
    """
    base_label = task_name if kind == Kind.CUSTOM and task_name else kind.value.capitalize()
    task_suffix = f"#{str(timestamp)[-3:]}"
    return f"{base_label} {task_suffix}"


def schedule_reminder(request: ReminderRequest) -> tuple[list[str], str]:
    """
    Schedule a one-time reminder with optional heads-up.

    Args:
        request: ReminderRequest with all scheduling details

    Returns:
        Tuple of (list of scheduled job IDs, formatted task label)
    """
    scheduler = get_scheduler()
    now = datetime.now(UTC)
    timestamp = int(now.timestamp())

    task_label = format_task_label(request.kind, request.task_name, timestamp)

    # Schedule main reminder
    main_time = now + request.duration
    main_job_id = _build_job_id(
        user_id=request.user_id,
        chat_id=request.chat_id,
        kind=request.kind.value,
        timestamp=timestamp,
        job_type="main",
    )
    main_message = f"⏰ {task_label} is ready!"

    scheduler.add_job(
        send_reminder,
        **as_apscheduler_date_args(request.duration, now=now, tz=UTC),
        id=main_job_id,
        kwargs={
            "chat_id": request.chat_id,
            "message": main_message,
            "webhook_url": request.webhook_url,
        },
        replace_existing=True,
    )

    job_ids = [main_job_id]
    logger.info(f"Scheduled main reminder: {main_job_id} at {main_time}")

    # Schedule heads-up reminder if requested
    if request.lead_time:
        try:
            from src.shared.utils.duration import parse_duration

            lead_td = parse_duration(request.lead_time)
            headsup_duration = request.duration - lead_td

            if headsup_duration.total_seconds() > 0:
                headsup_time = now + headsup_duration
                headsup_job_id = _build_job_id(
                    user_id=request.user_id,
                    chat_id=request.chat_id,
                    kind=request.kind.value,
                    timestamp=timestamp,
                    job_type="headsup",
                )
                headsup_message = (
                    f"🔔 {task_label} will be ready in {format_duration(lead_td)}"
                )

                scheduler.add_job(
                    send_reminder,
                    **as_apscheduler_date_args(headsup_duration, now=now, tz=UTC),
                    id=headsup_job_id,
                    kwargs={
                        "chat_id": request.chat_id,
                        "message": headsup_message,
                        "webhook_url": request.webhook_url,
                    },
                    replace_existing=True,
                )

                job_ids.append(headsup_job_id)
                logger.info(
                    f"Scheduled heads-up reminder: {headsup_job_id} at {headsup_time}"
                )
            else:
                logger.warning(
                    f"Heads-up time {request.lead_time} >= duration {format_duration(request.duration)}, skipping"
                )
        except ValueError as e:
            logger.error(f"Failed to parse lead_time '{request.lead_time}': {e}")

    return job_ids, task_label


def format_job_display(job_id: str, next_run_time: datetime) -> str:
    """
    Format a job for display in the list.

    Args:
        job_id: Job ID to parse (format: lw:user:chat:kind:timestamp:type)
        next_run_time: When the job will run

    Returns:
        Formatted string for display
    """
    parsed = _parse_job_id(job_id)
    if not parsed:
        logger.warning(f"Invalid job ID format: {job_id}")
        return f"⏰ Unknown - {next_run_time.strftime('%H:%M:%S')}"

    kind_str = parsed["kind"]
    timestamp_str = parsed["timestamp"]
    job_type = parsed["type"]

    local_dt = next_run_time.astimezone(ZoneInfo("America/Sao_Paulo"))
    next_run_time_formatted = local_dt.strftime("%a %H:%M")

    # Parse kind enum
    try:
        kind = Kind(kind_str)
    except ValueError:
        logger.warning(f"Unknown kind in job ID: {kind_str}")
        return f"⏰ Unknown - {next_run_time_formatted}"

    # Use same task label format as when scheduling
    try:
        task_label = format_task_label(kind, None, int(timestamp_str))
    except (ValueError, IndexError):
        logger.warning(f"Invalid timestamp in job ID: {timestamp_str}")
        return f"⏰ Unknown - {next_run_time_formatted}"

    # Add heads-up indicator for heads-up jobs
    if job_type == "headsup":
        task_label = f"{task_label} (heads-up)"

    emoji = "⏰" if job_type == "main" else "🔔"
    return f"{emoji} {task_label} - {next_run_time_formatted}"


def list_user_jobs(user_id: int, chat_id: int) -> list[dict]:
    """
    List all scheduled jobs for a user.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID

    Returns:
        List of job info dicts with id, next_run_time, and name
    """
    scheduler = get_scheduler()
    prefix = f"{_JOB_ID_PREFIX}:{user_id}:{chat_id}:"

    jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            jobs.append(
                {
                    "id": job.id,
                    "next_run_time": job.next_run_time,
                    "name": job.name,
                }
            )

    return sorted(jobs, key=lambda j: j["next_run_time"])


def cancel_job(job_id: str) -> bool:
    """
    Cancel a scheduled job by ID.

    Args:
        job_id: Job ID to cancel

    Returns:
        True if job was cancelled, False if not found
    """
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Cancelled job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        return False


def cancel_user_jobs(user_id: int, chat_id: int) -> int:
    """
    Cancel all scheduled jobs for a user.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID

    Returns:
        Number of jobs cancelled
    """
    jobs = list_user_jobs(user_id, chat_id)
    count = 0
    for job in jobs:
        if cancel_job(job["id"]):
            count += 1
    return count
