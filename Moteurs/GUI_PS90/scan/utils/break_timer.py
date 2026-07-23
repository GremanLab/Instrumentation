"""
This file is just here to manage time during a break in the scan. 
It allows to keep track of the total time spent in break mode, so 
that we can accurately estimate the total duration of the scan.
"""

import time


class BreakTimer:
    """Track cumulative pause time during a scan."""

    def __init__(self):
        self.total = 0.0
        self._active = False
        self._started_at = None

    def start(self, started_at=None):
        if self._active:
            return self.total
        self._active = True
        self._started_at = time.time() if started_at is None else started_at
        return self.total

    def stop(self, stopped_at=None):
        if not self._active:
            return self.total
        if stopped_at is None:
            stopped_at = time.time()
        self.total += stopped_at - self._started_at
        self._active = False
        self._started_at = None
        return self.total

    def elapsed(self, now=None):
        """Return the total break time including the currently active pause."""
        if now is None:
            now = time.time()
        if self._active:
            return self.total + (now - self._started_at)
        return self.total

    def is_active(self):
        return self._active
