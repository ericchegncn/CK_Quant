"""Synthetic iceberg order sizing.

The exchange only sees one child order at a time.  State persistence and order
submission stay in :mod:`freqtrade.freqtradebot`; this module deliberately
contains only deterministic configuration and sizing logic so it is easy to
test and audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random, SystemRandom
from typing import Any


@dataclass(frozen=True)
class IcebergSettings:
    enabled: bool = False
    entry: bool = True
    exit: bool = True
    visible_ratio: float = 0.1
    max_slices: int = 10
    min_slice_stake: float = 0.0
    replenish_interval: float = 5.0
    size_jitter: float = 0.0

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> IcebergSettings:
        raw = config.get("iceberg_orders") or {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            entry=bool(raw.get("entry", True)),
            exit=bool(raw.get("exit", True)),
            visible_ratio=float(raw.get("visible_ratio", 0.1)),
            max_slices=int(raw.get("max_slices", 10)),
            min_slice_stake=float(raw.get("min_slice_stake", 0.0)),
            replenish_interval=float(raw.get("replenish_interval", 5.0)),
            size_jitter=float(raw.get("size_jitter", 0.0)),
        )

    def slice_stake(
        self,
        remaining_stake: float,
        total_stake: float,
        *,
        rng: Random | None = None,
    ) -> float:
        """Return the next visible child stake without exceeding the remainder."""
        if remaining_stake <= 0 or total_stake <= 0:
            return 0.0

        base = max(
            total_stake * self.visible_ratio,
            total_stake / self.max_slices,
            self.min_slice_stake,
        )
        if self.size_jitter:
            # Only increase the base slice.  This preserves max_slices as a hard
            # upper bound while making the visible sizes less repetitive.
            source = rng or SystemRandom()
            base *= 1.0 + source.uniform(0.0, self.size_jitter)
        return min(remaining_stake, base)
