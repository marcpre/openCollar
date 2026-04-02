from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BrowserAutomation:
    """Prepared Playwright holder for future browser-facing tools."""

    started: bool = False

    def ensure_started(self) -> None:
        self.started = True
