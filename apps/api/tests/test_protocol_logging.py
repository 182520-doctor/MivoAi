from app.core.protocol_logging import redact_protocol_value


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
