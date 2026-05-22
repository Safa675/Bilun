"""Validation errors for exact SUT claim datasets."""

from __future__ import annotations


class ClaimValidationError(ValueError):
    """Raised when exact claim Parquet inputs fail runtime validation."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        message = "SUT claim dataset validation failed"
        if self.errors:
            message = f"{message}: " + "; ".join(self.errors)
        super().__init__(message)
