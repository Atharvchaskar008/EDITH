"""Re-run the pipeline on a fixed interval so the picture stays current."""

from __future__ import annotations

from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from fusion import config


class Monitor:
    """Calls `start_run` every SCHEDULER_INTERVAL_HOURS. `start_run` must return
    at once and refuse to overlap a run that is already in progress."""

    def __init__(self, start_run: Callable[[], object], interval_hours: Optional[float] = None):
        self._start_run = start_run
        self._interval_hours = interval_hours or config.SCHEDULER_INTERVAL_HOURS
        self._scheduler: Optional[BackgroundScheduler] = None

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def start(self) -> None:
        if self.running:
            return
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            self._start_run, "interval", hours=self._interval_hours, id="pipeline",
            max_instances=1, coalesce=True,
        )
        self._scheduler.start()

    def stop(self) -> None:
        if self.running:
            self._scheduler.shutdown(wait=False)
        self._scheduler = None

    def next_run(self) -> Optional[str]:
        if not self.running:
            return None
        job = self._scheduler.get_job("pipeline")
        if job is None or job.next_run_time is None:
            return None
        return job.next_run_time.isoformat().replace("+00:00", "Z")
