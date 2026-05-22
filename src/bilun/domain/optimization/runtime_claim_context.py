"""Request-local exact claim contexts for SUT optimization functions."""

from __future__ import annotations

from contextvars import ContextVar, Token
from types import TracebackType

from .claim_context import CopayRateClaimContext, SurchargeClaimContext


_surcharge_context: ContextVar[SurchargeClaimContext | None] = ContextVar(
    "sut_surcharge_context", default=None
)
_copay_rate_context: ContextVar[CopayRateClaimContext | None] = ContextVar(
    "sut_copay_rate_context", default=None
)


def get_surcharge_context() -> SurchargeClaimContext | None:
    return _surcharge_context.get()


def get_copay_rate_context() -> CopayRateClaimContext | None:
    return _copay_rate_context.get()


class ClaimContextManager:
    """Temporarily expose exact claim contexts to legacy optimization call sites."""

    def __init__(
        self,
        *,
        surcharge: SurchargeClaimContext | None = None,
        copay_rate: CopayRateClaimContext | None = None,
    ) -> None:
        self._surcharge = surcharge
        self._copay_rate = copay_rate
        self._surcharge_token: Token[SurchargeClaimContext | None] | None = None
        self._copay_rate_token: Token[CopayRateClaimContext | None] | None = None

    def __enter__(self) -> "ClaimContextManager":
        self._surcharge_token = _surcharge_context.set(self._surcharge)
        self._copay_rate_token = _copay_rate_context.set(self._copay_rate)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._copay_rate_token is not None:
            _copay_rate_context.reset(self._copay_rate_token)
        if self._surcharge_token is not None:
            _surcharge_context.reset(self._surcharge_token)
