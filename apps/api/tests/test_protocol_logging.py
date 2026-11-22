import io
import logging

from app.shared.protocol_logging import SafeStreamHandler, redact_protocol_value


def test_protocol_logging_redacts_sensitive_fields():
    value = {
        "account": {"email": "person@example.com", "accessToken": "secret-value"},
        "params": {"refreshToken": False, "message": "你好"},
    }

    redacted = redact_protocol_value(value)

    assert redacted["account"]["email"] == "[REDACTED]"
    assert redacted["account"]["accessToken"] == "[REDACTED]"
    assert redacted["params"]["refreshToken"] == "[REDACTED]"
    assert redacted["params"]["message"] == "你好"


def test_protocol_console_handler_survives_unencodable_text():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="gbk")
    handler = SafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "启动失败：\ufffd",
        (),
        None,
    )

    handler.emit(record)
    stream.flush()

    assert raw.getvalue()
