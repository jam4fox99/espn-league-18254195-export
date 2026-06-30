from __future__ import annotations

from mygm_worker.jobs.retry import RetryDisposition, classify_retry


def test_retry_classifier_marks_rate_limits_server_and_network_failures_retryable() -> None:
    assert classify_retry(429, None).disposition is RetryDisposition.RETRYABLE
    assert classify_retry(503, None).disposition is RetryDisposition.RETRYABLE
    assert classify_retry(None, "network").disposition is RetryDisposition.RETRYABLE


def test_retry_classifier_marks_credential_failures_terminal_for_credentials() -> None:
    assert classify_retry(401, None).disposition is RetryDisposition.CREDENTIAL_FAILURE
    assert classify_retry(403, None).disposition is RetryDisposition.CREDENTIAL_FAILURE


def test_retry_classifier_marks_other_client_errors_terminal() -> None:
    assert classify_retry(404, None).disposition is RetryDisposition.TERMINAL_FAILURE
