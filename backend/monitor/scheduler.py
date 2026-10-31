"""Scheduled monitoring with APScheduler.

How duplicate/overlapping checks are prevented
----------------------------------------------
A single "tick" job runs every SCHEDULER_TICK_SECONDS. For each due API it runs an
atomic `UPDATE ... WHERE id=? AND next_check_at <= now` that pushes `next_check_at`
forward by the API's interval. Only the process whose UPDATE touched a row runs the
check, so even if several Django/gunicorn processes (or several schedulers) are
running, each check executes exactly once per interval. An in-process "in flight"
set adds a second guard, and timeout < interval is enforced by validation.
"""
import atexit
import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_in_flight = set()
_scheduler = None
_executor = None


def _check_one(pk):
    from .models import MonitoredAPI
    from .services.checker import check_api

    try:
        api = MonitoredAPI.objects.get(pk=pk)
        check_api(api)
    except MonitoredAPI.DoesNotExist:
        pass
    except Exception:
        logger.exception("Scheduled check failed for api=%s", pk)
    finally:
        with _lock:
            _in_flight.discard(pk)
        close_old_connections()


def run_due_checks():
    from .models import MonitoredAPI

    try:
        now = timezone.now()
        due = list(
            MonitoredAPI.objects.filter(is_active=True, next_check_at__lte=now)
            .order_by("next_check_at")
            .values_list("pk", "interval_seconds")[:500]
        )
        for pk, interval in due:
            with _lock:
                if pk in _in_flight:
                    continue
            claimed = MonitoredAPI.objects.filter(pk=pk, is_active=True, next_check_at__lte=now).update(
                next_check_at=now + timedelta(seconds=interval)
            )
            if claimed:
                with _lock:
                    _in_flight.add(pk)
                _executor.submit(_check_one, pk)
    except Exception:
        logger.exception("Scheduler tick failed")
    finally:
        close_old_connections()


def prune_old_checks():
    from .models import CheckResult

    try:
        cutoff = timezone.now() - timedelta(days=settings.CHECK_RETENTION_DAYS)
        deleted, _ = CheckResult.objects.filter(checked_at__lt=cutoff).delete()
        logger.info("Pruned %s old check results", deleted)
    except Exception:
        logger.exception("Pruning failed")
    finally:
        close_old_connections()


def start_scheduler(blocking=False):
    """Start the scheduler. Safe to call twice in one process (second call is a no-op)."""
    global _scheduler, _executor
    if _scheduler is not None:
        return _scheduler
    _executor = ThreadPoolExecutor(max_workers=settings.CHECK_WORKERS, thread_name_prefix="trustroute-check")
    _scheduler = BlockingScheduler() if blocking else BackgroundScheduler()
    _scheduler.add_job(
        run_due_checks, "interval", seconds=settings.SCHEDULER_TICK_SECONDS,
        id="trustroute-tick", max_instances=1, coalesce=True, replace_existing=True,
    )
    _scheduler.add_job(
        prune_old_checks, "cron", hour=3, minute=15,
        id="trustroute-prune", max_instances=1, coalesce=True, replace_existing=True,
    )
    atexit.register(stop_scheduler)
    logger.info("Starting TrustRoute scheduler (tick=%ss, workers=%s)", settings.SCHEDULER_TICK_SECONDS, settings.CHECK_WORKERS)
    if blocking:
        def _terminate(signum, frame):
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _terminate)
    _scheduler.start()
    return _scheduler


def stop_scheduler():
    global _scheduler, _executor
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
