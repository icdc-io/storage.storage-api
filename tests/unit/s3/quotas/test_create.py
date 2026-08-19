from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.s3_quota import S3Quotas, S3QuotaSchema
from tests.factories.s3_quota import S3QuotaPayloadFactory


def make_create_quota_body(**overrides):
    defaults = {
        "account_id": 1,
        "pool_id": 1,
    }
    defaults.update(overrides)
    return S3QuotaPayloadFactory.build(
        constrained_limits=True,
        **defaults,
    )


def make_limitset(*, users=10, buckets=20, objects=30, data_size_mb=200):
    return SimpleNamespace(
        users=users,
        buckets=buckets,
        objects=objects,
        data_size_mb=data_size_mb,
    )


@pytest.fixture
def quota_limits(monkeypatch):
    monkeypatch.setattr(
        S3QuotaSchema,
        "_S3QuotaSchema__get_pool",
        lambda self, pool_id: SimpleNamespace(id=pool_id),
    )
    monkeypatch.setattr(
        S3Quotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset()),
    )


# Field validation


@pytest.mark.parametrize("field", ["users", "buckets", "objects", "data_size_mb"])
def test_s3_quota_schema_accepts_valid_quota_field(field, quota_limits):
    loaded = S3QuotaSchema().load(make_create_quota_body(**{field: 1}))

    assert loaded[field] == 1


@pytest.mark.parametrize("field", ["users", "buckets", "objects", "data_size_mb"])
@pytest.mark.parametrize("value", [-1, "bad", None])
def test_s3_quota_schema_rejects_invalid_quota_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema().load(make_create_quota_body(**{field: value}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize("field", ["account_id", "pool_id"])
def test_s3_quota_schema_accepts_valid_id_field(field, quota_limits):
    loaded = S3QuotaSchema().load(make_create_quota_body(**{field: 2}))

    assert loaded[field] == 2


@pytest.mark.parametrize("field", ["account_id", "pool_id"])
@pytest.mark.parametrize("value", ["bad", None])
def test_s3_quota_schema_rejects_invalid_id_field(field, value, quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema().load(make_create_quota_body(**{field: value}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "missing_field",
    ["users", "buckets", "objects", "data_size_mb", "account_id", "pool_id"],
)
def test_s3_quota_schema_rejects_missing_required_field(missing_field, quota_limits):
    body = make_create_quota_body()
    body.pop(missing_field)

    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema().load(body)

    assert missing_field in exc_info.value.messages


def test_s3_quota_schema_rejects_extra_field(quota_limits):
    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema().load(make_create_quota_body(extra_field="nope"))

    assert "extra_field" in exc_info.value.messages


def test_s3_quota_schema_rejects_unknown_pool(monkeypatch):
    monkeypatch.setattr(
        S3QuotaSchema,
        "_S3QuotaSchema__get_pool",
        lambda self, pool_id: (_ for _ in ()).throw(ValidationError("Must exist.", "pool")),
    )

    with pytest.raises(ValidationError) as exc_info:
        S3QuotaSchema().load(make_create_quota_body(pool_id=999))

    assert "Must exist." in str(exc_info.value.messages)


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
def test_s3_quota_schema_rejects_value_over_pool_limit(
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
        S3QuotaSchema().load(make_create_quota_body(**{field: requested}))

    assert field in exc_info.value.messages


@pytest.mark.parametrize(
    "field, limit",
    [
        ("users", 10),
        ("buckets", 20),
        ("objects", 30),
        ("data_size_mb", 200),
    ],
)
def test_s3_quota_schema_accepts_value_at_pool_limit(
    field,
    limit,
    monkeypatch,
    quota_limits,
):
    monkeypatch.setattr(
        S3Quotas,
        "get_pool_limitset",
        classmethod(lambda cls, pool_id: make_limitset(**{field: limit})),
    )

    loaded = S3QuotaSchema().load(make_create_quota_body(**{field: limit}))

    assert loaded[field] == limit


@pytest.mark.parametrize(
    "field, usage, requested",
    [
        ("users", 4, 3),
        ("buckets", 7, 6),
        ("objects", 12, 11),
        ("data_size_mb", 50, 49),
    ],
)
def test_s3_quota_schema_rejects_value_below_current_usage(
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
        }
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_create_quota_body(**{field: requested}))

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
def test_s3_quota_schema_accepts_value_equal_to_current_usage(
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
        }
    )

    loaded = schema.load(make_create_quota_body(**{field: usage}))

    assert loaded[field] == usage
