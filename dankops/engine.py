from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable

from .config import AppConfig

SendMessage = Callable[[str], Awaitable[None]]


@dataclass
class EngineStats:
    running: bool
    sent_total: int
    sent_by_command: dict[str, int]
    last_sent_ts: float
    next_due_by_command: dict[str, float]
    on_break: bool


class FarmEngine:
    def __init__(self, config: AppConfig, send_message: SendMessage):
        self._config = config
        self._send_message = send_message
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._running = False
        self._sent_total = 0
        self._sent_by_command: dict[str, int] = defaultdict(int)
        self._next_due_by_command: dict[str, float] = {}
        self._last_sent_ts = 0.0
        self._on_break = False
        now = time.monotonic()
        for name, profile in config.commands.items():
            delay = random.uniform(profile.min_delay, profile.max_delay)
            self._next_due_by_command[name] = now + max(1.0, delay)

    def update_config(self, config: AppConfig) -> None:
        self._config = config
        now = time.monotonic()
        for name, profile in config.commands.items():
            if name not in self._next_due_by_command:
                self._next_due_by_command[name] = now + random.uniform(profile.min_delay, profile.max_delay)

    async def start(self) -> bool:
        async with self._lock:
            if self._running:
                return False
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            return True

    async def stop(self) -> bool:
        async with self._lock:
            if not self._running:
                return False
            self._running = False
            task = self._task
            self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._on_break = False
        return True

    async def run_once(self, command_name: str) -> bool:
        profile = self._config.commands.get(command_name)
        if profile is None or not profile.enabled:
            return False
        await self._send_message(profile.command)
        self._sent_total += 1
        self._sent_by_command[command_name] += 1
        self._last_sent_ts = time.monotonic()
        self._next_due_by_command[command_name] = self._last_sent_ts + random.uniform(profile.min_delay, profile.max_delay)
        return True

    def get_stats(self) -> EngineStats:
        return EngineStats(
            running=self._running,
            sent_total=self._sent_total,
            sent_by_command=dict(self._sent_by_command),
            last_sent_ts=self._last_sent_ts,
            next_due_by_command=dict(self._next_due_by_command),
            on_break=self._on_break,
        )

    async def _run_loop(self) -> None:
        next_break_start = self._next_break_start(time.monotonic())
        while self._running:
            now = time.monotonic()
            if self._config.break_mode and now >= next_break_start:
                self._on_break = True
                duration = random.uniform(self._config.break_duration_min_minutes, self._config.break_duration_max_minutes) * 60.0
                await asyncio.sleep(max(1.0, duration))
                self._on_break = False
                next_break_start = self._next_break_start(time.monotonic())
                continue
            due_name = self._pick_due_command(now)
            if due_name is not None:
                profile = self._config.commands[due_name]
                await self._send_message(profile.command)
                sent_at = time.monotonic()
                self._sent_total += 1
                self._sent_by_command[due_name] += 1
                self._last_sent_ts = sent_at
                self._next_due_by_command[due_name] = sent_at + random.uniform(profile.min_delay, profile.max_delay)
                jitter = random.uniform(self._config.command_interval.min_seconds, self._config.command_interval.max_seconds)
                await asyncio.sleep(max(0.1, jitter))
                continue
            sleep_seconds = self._seconds_until_next_due(now)
            await asyncio.sleep(max(0.2, min(2.5, sleep_seconds)))

    def _next_break_start(self, now: float) -> float:
        minutes = random.uniform(self._config.break_after_min_minutes, self._config.break_after_max_minutes)
        return now + max(1.0, minutes * 60.0)

    def _pick_due_command(self, now: float) -> str | None:
        due = []
        for name, profile in self._config.commands.items():
            if not profile.enabled:
                continue
            next_due = self._next_due_by_command.get(name, now)
            if next_due <= now:
                due.append(name)
        if not due:
            return None
        random.shuffle(due)
        return due[0]

    def _seconds_until_next_due(self, now: float) -> float:
        next_items = []
        for name, profile in self._config.commands.items():
            if not profile.enabled:
                continue
            next_items.append(self._next_due_by_command.get(name, now + 5))
        if not next_items:
            return 1.0
        return max(0.2, min(next_items) - now)
