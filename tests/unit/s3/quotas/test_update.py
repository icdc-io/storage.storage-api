import pytest
from marshmallow import ValidationError

from app.models.s3_quota import S3Quotas, S3QuotaSchema
from tests.factories.s3_quota import S3QuotaUpdatePayloadFactory
from tests.unit.s3.quotas.test_create import make_limitset, quota_limits


def make_update_quota_body(**overrides):
    body = S3QuotaUpdatePayloadFactory.build(pool_id=1)
    body.update(overrides)
    return body


# Field validation


def test_update_s3_quota_schema_accepts_empty_payload():
    loaded = S3QuotaSchema(partial=True).load({})

    assert loaded == {}


@pytest.mark.parametrize("field", ["users", "buckets", "objects", "data_size_mb"])
def test_update_s3_quota_schema_accepts_valid_quota_field(field, quota_limits):
    loaded = S3QuotaSchema(partial=True).load(make_update_quota_body(**{field: 1}))

    assert loaded[field] == 1


@pytest.mark.parametrize("field", ["users", "buckets", "objects", "data_size_mb"])
@pytest.mark.parametrize("value", [-1, "bad", None])
def test_update_s3_quota_schema_rejects_invalid_quota_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema(partial=True).load(make_update_quota_body(**{field: value}))

    assert field in exc_info.value.messages


def test_update_s3_quota_schema_rejects_unknown_field(quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema(partial=True).load(make_update_quota_body(extra_field="nope"))

    assert "extra_field" in exc_info.value.messages


def test_update_s3_quota_schema_accepts_without_pool_context():
    loaded = S3QuotaSchema(partial=True).load({"users": 5})

    assert loaded == {"users": 5}


# Limit and usage validation


@pytest.mark.parametrize(
    "field, limit, requested",
    [
        ("users", 10, 11),
        ("buckets", 20, 21),
        ("objects", 30, 31),
        ("data_size_mb", 200, 201),
    ],
)
def test_update_s3_quota_schema_rejects_value_over_pool_limit(
    field,
    limit,
    requested,
    monkeypatch,
    quota_limits,
):
    monkeypatch.setattr(
        S3Quotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset(**{field: limit})),
    )

    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema(partial=True).load(make_update_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, usage, requested",
    [
        ("users", 4, 3),
        ("buckets", 7, 6),
        ("objects", 12, 11),
        ("data_size_mb", 50, 49),
    ],
)
def test_update_s3_quota_schema_rejects_value_below_current_usage(
    field,
    usage,
    requested,
    quota_limits,
):
    schema = S3QuotaSchema(
        context={
            "usage": {
                "users": 0,
                "buckets": 0,
                "objects": 0,
                "data_size_mb": 0,
            }
            | {field: usage}
        },
        partial=True,
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_update_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, usage",
    [
        ("users", 4),
        ("buckets", 7),
        ("objects", 12),
        ("data_size_mb", 50),
    ],
)
def test_update_s3_quota_schema_accepts_value_equal_to_current_usage(
    field,
    usage,
    quota_limits,
):
    schema = S3QuotaSchema(
        context={
            "usage": {
                "users": 0,
                "buckets": 0,
                "objects": 0,
                "data_size_mb": 0,
            }
            | {field: usage}
        },
        partial=True,
    )

    loaded = schema.load(make_update_quota_body(**{field: usage}))

    assert loaded[field] == usage
