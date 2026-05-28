from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class NavState(str, Enum):
    COMBAT = "combat"
    WAIT_TARGET = "wait_target"
    COOLDOWN = "cooldown"
    MOVE_TO_ANCHOR = "move_to_anchor"
    EXEC_ACTION = "exec_action"


@dataclass
class NavContext:
    now_ts: float
    char_pos: Optional[tuple[int, int]]
    hunters_pos: list[tuple[int, int]]
    anchor_points: dict[str, int]


class NavigationStateMachine:
    """Small deterministic navigator for patrol commands.

    - Keeps combat and patrol phases separated.
    - Resolves anchors to a concrete x each frame.
    - Emits one patrol command at a time with cooldown control.
    """

    def __init__(
        self,
        steps: list[dict[str, Any]],
        no_hunter_timeout_sec: float,
        command_cooldown_sec: float,
        move_tolerance_px: int,
    ) -> None:
        self.steps = steps
        self.no_hunter_timeout_sec = max(0.1, float(no_hunter_timeout_sec))
        self.command_cooldown_sec = max(0.05, float(command_cooldown_sec))
        self.move_tolerance_px = max(1, int(move_tolerance_px))

        self._last_hunter_seen_ts = 0.0
        self._step_idx = 0
        self._next_ready_ts = 0.0
        self._state: NavState = NavState.WAIT_TARGET

    @property
    def state(self) -> NavState:
        return self._state

    def next_command(self, ctx: NavContext) -> Optional[dict[str, Any]]:
        if ctx.hunters_pos:
            self._last_hunter_seen_ts = ctx.now_ts
            self._state = NavState.COMBAT
            return None

        if not self.steps or ctx.char_pos is None:
            self._state = NavState.WAIT_TARGET
            return None

        if (ctx.now_ts - self._last_hunter_seen_ts) < self.no_hunter_timeout_sec:
            self._state = NavState.WAIT_TARGET
            return None

        if ctx.now_ts < self._next_ready_ts:
            self._state = NavState.COOLDOWN
            return None

        step = self.steps[self._step_idx % len(self.steps)]
        action = str(step.get("action", "")).strip().lower()

        if action == "move":
            self._state = NavState.MOVE_TO_ANCHOR
            return self._handle_move_step(ctx, step)

        if action == "wait":
            wait_sec = float(step.get("wait_sec", self.command_cooldown_sec))
            self._advance(wait_sec)
            self._state = NavState.EXEC_ACTION
            return {"action": "wait"}

        cmd = dict(step)
        resolved_x = self._resolve_step_x(ctx, step)
        if isinstance(resolved_x, int):
            cmd["x"] = resolved_x

        hold_sec = float(step.get("hold_sec", 0.0))
        wait_sec = float(step.get("wait_sec", 0.0))
        cooldown = max(self.command_cooldown_sec, hold_sec, wait_sec)
        self._advance(cooldown)
        self._state = NavState.EXEC_ACTION
        return cmd

    def _handle_move_step(self, ctx: NavContext, step: dict[str, Any]) -> Optional[dict[str, Any]]:
        char_x, _ = ctx.char_pos or (None, None)
        if char_x is None:
            return None

        target_x = self._resolve_step_x(ctx, step)
        if target_x is None:
            # Invalid step, skip to avoid dead loop.
            self._advance(self.command_cooldown_sec)
            return None

        tol = int(step.get("tol", self.move_tolerance_px))
        cmd = {"action": "move", "x": int(target_x), "tol": max(1, tol)}
        if abs(char_x - int(target_x)) <= max(1, tol):
            self._advance(self.command_cooldown_sec)
        return cmd

    def _advance(self, cooldown_sec: float) -> None:
        self._step_idx += 1
        self._next_ready_ts = self._next_ready_ts + max(0.0, cooldown_sec)
        # If next_ready has not been initialized or drifts behind now, reset at call-site.

    def sync_clock(self, now_ts: float) -> None:
        if self._next_ready_ts < now_ts:
            self._next_ready_ts = now_ts

    def _resolve_step_x(self, ctx: NavContext, step: dict[str, Any]) -> Optional[int]:
        raw_x = step.get("x")
        if isinstance(raw_x, (int, float)):
            return int(raw_x)

        anchor = step.get("anchor")
        if isinstance(anchor, str):
            anchored = self._resolve_anchor(ctx, anchor)
            if anchored is not None:
                return anchored

        return None

    def _resolve_anchor(self, ctx: NavContext, anchor: str) -> Optional[int]:
        key = anchor.strip()
        if not key:
            return None

        # 1) explicit global anchor table.
        val = ctx.anchor_points.get(key)
        if isinstance(val, int):
            return val

        # 2) namespaced anchors: e.g. L1.left_x / L1.left
        if "." in key:
            layer, field = key.split(".", 1)
            norm_field = self._normalize_field_name(field)
            namespaced = f"{layer}.{norm_field}"
            val = ctx.anchor_points.get(namespaced)
            if isinstance(val, int):
                return val

        return None

    @staticmethod
    def _normalize_field_name(field: str) -> str:
        text = field.strip().lower()
        alias = {
            "left": "left_x",
            "right": "right_x",
            "drop": "drop_x",
            "rope": "rope_x",
        }
        if text in alias:
            return alias[text]
        if text.endswith("_x"):
            return text
        return text

