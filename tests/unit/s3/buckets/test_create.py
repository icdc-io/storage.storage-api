from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.bucket import BucketSchema
from tests.factories.bucket import (
    SMALL_BUCKET_QUOTA,
    TYPICAL_BUCKET_QUOTA,
    UNLIMITED_BUCKET_QUOTA,
    BucketCreatePayloadFactory,
)


def make_s3_user(*, data_size_mb=100, objects=50):
    return SimpleNamespace(
        quota={"data_size_mb": data_size_mb, "objects": objects},
    )


def make_create_bucket_body(**overrides):
    body = BucketCreatePayloadFactory.build(
        typical_quota=True,
        name="team-bucket",
        user_name="unitacct$user_1",
    )
    body.update(overrides)
    return body


def make_create_schema(*, user=None):
    if user is None:
        return BucketSchema()
    return BucketSchema(context={"user": user})


# Field validation


@pytest.mark.parametrize(
    "valid_name",
    [
        "team-bucket",
        "bucket-01",
        "bucket.with.dots",
        "a" * 63,
    ],
)
def test_bucket_schema_accepts_valid_name(valid_name):
    loaded = make_create_schema(user=make_s3_user()).load(
        make_create_bucket_body(name=valid_name)
    )

    assert loaded["name"] == valid_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "ab",
        "A-bucket",
        "bucket_with_underscore",
        "192.168.0.1",
        "bucket..dots",
        "xn--bucket",
        "bucket/slash",
        "",
        None,
        "a" * 64,
    ],
)
def test_bucket_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user()).load(
            make_create_bucket_body(name=invalid_name)
        )

    assert "name" in exc_info.value.messages or "Name" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_user_name",
    ["unitacct$user_1", "user_1", "team$user.name"],
)
def test_bucket_schema_accepts_valid_user_name(valid_user_name):
    loaded = make_create_schema(user=make_s3_user()).load(
        make_create_bucket_body(user_name=valid_user_name)
    )

    assert loaded["user_name"] == valid_user_name


@pytest.mark.parametrize("invalid_user_name", [None])
def test_bucket_schema_rejects_invalid_user_name(invalid_user_name):
    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user()).load(
            make_create_bucket_body(user_name=invalid_user_name)
        )

    assert "user_name" in exc_info.value.messages


@pytest.mark.parametrize("missing_field", ["name", "user_name"])
def test_bucket_schema_rejects_missing_required_field(missing_field):
    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user()).load(
            make_create_bucket_body(**{missing_field: None})
        )

    assert missing_field in exc_info.value.messages


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_bucket_schema_rejects_unknown_field(unknown_field):
    payload = make_create_bucket_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user()).load(payload)

    assert unknown_field in exc_info.value.messages


# Quota validation


def test_bucket_schema_accepts_create_without_user_context():
    quota = TYPICAL_BUCKET_QUOTA.copy()

    loaded = BucketSchema().load(make_create_bucket_body(quota=quota))

    assert loaded["quota"] == quota


def test_bucket_schema_accepts_valid_quota():
    quota = TYPICAL_BUCKET_QUOTA.copy()

    loaded = make_create_schema(user=make_s3_user()).load(
        make_create_bucket_body(quota=quota)
    )

    assert loaded["quota"] == quota


@pytest.mark.parametrize(
    "quota, invalid_field",
    [
        ({"data_size_mb": -2, "objects": 5}, "data_size_mb"),
        ({"data_size_mb": 10, "objects": -2}, "objects"),
        ({"data_size_mb": "bad", "objects": 5}, "data_size_mb"),
        ({"data_size_mb": 10, "objects": "bad"}, "objects"),
        ({"data_size_mb": 10, "objects": 5, "buckets": 1}, "quota"),
    ],
)
def test_bucket_schema_rejects_invalid_quota_values(quota, invalid_field):
    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user()).load(
            make_create_bucket_body(quota=quota)
        )

    if invalid_field == "quota":
        assert invalid_field in exc_info.value.messages
    else:
        assert invalid_field in exc_info.value.messages["quota"]


def test_bucket_schema_accepts_unlimited_quota():
    loaded = make_create_schema(user=make_s3_user()).load(
        make_create_bucket_body(quota=UNLIMITED_BUCKET_QUOTA.copy())
    )

    assert loaded["quota"] == UNLIMITED_BUCKET_QUOTA


def test_bucket_schema_accepts_quota_at_user_boundary():
    loaded = make_create_schema(user=make_s3_user(data_size_mb=10, objects=5)).load(
        make_create_bucket_body(quota={"data_size_mb": 10, "objects": 5})
    )

    assert loaded["quota"] == {"data_size_mb": 10, "objects": 5}


def test_bucket_schema_rejects_quota_above_user_quota():
    with pytest.raises(ValidationError) as exc_info:
        make_create_schema(user=make_s3_user(data_size_mb=5, objects=2)).load(
            make_create_bucket_body(quota={"data_size_mb": 10, "objects": 5})
        )

    assert exc_info.value.messages == {
        "data_size_mb": "Bucket quota 'data_size_mb' must not exceed user quota.",
        "objects": "Bucket quota 'objects' must not exceed user quota.",
    }


def test_bucket_schema_accepts_small_quota_from_factory():
    loaded = make_create_schema(user=make_s3_user()).load(
        make_create_bucket_body(quota=SMALL_BUCKET_QUOTA.copy())
    )

    assert loaded["quota"] == SMALL_BUCKET_QUOTA
