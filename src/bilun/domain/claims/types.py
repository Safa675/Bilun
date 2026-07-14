"""Shared typing aliases for exact SUT claim loading."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

RowDict = Mapping[str, Any]

__all__ = ["RowDict"]
