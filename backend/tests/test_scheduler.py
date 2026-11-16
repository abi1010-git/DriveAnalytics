from datetime import datetime, timedelta

from pipeline.scheduler import Job, run


def test_jobs_run_when_due_and_failures_wait_their_turn():
    now = [datetime(2026, 11, 16, 6, 0)]
    calls = []
    def ok():
        calls.append("live")
        return "fine"
    def broken():
        calls.append("daily")
        raise RuntimeError("portal down")
    jobs = [Job("live", timedelta(minutes=10), ok), Job("daily", timedelta(hours=24), broken)]
    logs = []
    def sleep(_):
        now[0] += timedelta(minutes=5)
    run(jobs, clock=lambda: now[0], sleep=sleep, log=logs.append, max_ticks=5)  # covers 20 minutes
    assert calls.count("live") == 3 and calls.count("daily") == 1
    assert any("daily: FAILED RuntimeError: portal down" in line for line in logs)
