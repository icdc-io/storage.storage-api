import pytest
from marshmallow import ValidationError


def assert_no_content_response(status, body):
    assert status == 204
    assert body in (None, "", {})


def assert_schema_response(
    body,
    schema,
    *,
    many=False,
    message="Response schema validation failed",
):
    try:
        schema(many=many).load(body)
    except ValidationError as exc:
        pytest.fail(f"{message}: {exc.messages}")
