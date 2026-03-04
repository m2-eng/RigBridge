"""Tests für Secret-Redaction im Logging."""

import logging

from src.backend.config.logger import SecretRedactionFilter


def test_secret_redaction_filter_masks_sensitive_values():
    log_filter = SecretRedactionFilter()
    record = logging.LogRecord(
        name='test',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='api_key=abc123 token=xyz789 password=hunter2',
        args=(),
        exc_info=None,
    )

    log_filter.filter(record)

    assert 'abc123' not in record.msg
    assert 'xyz789' not in record.msg
    assert 'hunter2' not in record.msg
    assert 'api_key=***' in record.msg
    assert 'token=***' in record.msg
    assert 'password=***' in record.msg
