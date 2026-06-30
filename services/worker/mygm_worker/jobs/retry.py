from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RetryDisposition(StrEnum):
    RETRYABLE = "retryable"
    CREDENTIAL_FAILURE = "credential_failure"
    TERMINAL_FAILURE = "terminal_failure"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    disposition: RetryDisposition
    reason: str


def classify_retry(status_code: int | None, error_kind: str | None) -> RetryDecision:
    if status_code in {401, 403}:
        return RetryDecision(RetryDisposition.CREDENTIAL_FAILURE, "credential rejected")
    if status_code == 429:
        return RetryDecision(RetryDisposition.RETRYABLE, "rate limited")
    if status_code is not None and 500 <= status_code <= 599:
        return RetryDecision(RetryDisposition.RETRYABLE, "server error")
    if error_kind in {"network", "timeout", "connection"}:
        return RetryDecision(RetryDisposition.RETRYABLE, "network failure")
    return RetryDecision(RetryDisposition.TERMINAL_FAILURE, "not retryable")
