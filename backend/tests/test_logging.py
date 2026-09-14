import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_produces_valid_json_with_extra_fields():
    record = logging.LogRecord(
        name="app.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="http_request",
        args=(),
        exc_info=None,
    )
    record.status_code = 201
    record.tenant_id = "tenant-a"

    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "app.access"
    assert parsed["message"] == "http_request"
    assert parsed["status_code"] == 201
    assert parsed["tenant_id"] == "tenant-a"


def test_json_formatter_includes_exception_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="algo falló",
            args=(),
            exc_info=True,
        )
        import sys

        record.exc_info = sys.exc_info()

    parsed = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in parsed["exception"]


def test_middleware_logs_a_structured_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/health")
    assert resp.status_code == 200

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    record = records[0]
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200
    assert record.tenant_id is None
    assert isinstance(record.duration_ms, float)


def test_middleware_resolves_tenant_id_from_a_valid_bearer_token(client, auth_headers, caplog):
    headers = auth_headers()
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/assets", headers=headers)
    assert resp.status_code == 200

    records = [r for r in caplog.records if r.name == "app.access" and r.path == "/assets"]
    assert len(records) == 1
    assert records[0].tenant_id is not None


def test_middleware_leaves_tenant_id_none_on_a_malformed_bearer_token(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/assets", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401

    records = [r for r in caplog.records if r.name == "app.access" and r.path == "/assets"]
    assert len(records) == 1
    assert records[0].tenant_id is None
