from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.bucket import Bucket, BucketSchema
from tests.factories.bucket import (
    SMALL_BUCKET_QUOTA,
    TYPICAL_BUCKET_QUOTA,
    UNLIMITED_BUCKET_QUOTA,
)


def make_s3_user(*, data_size_mb=100, objects=50):
    return SimpleNamespace(
        quota={"data_size_mb": data_size_mb, "objects": objects},
    )


def make_bucket(*, quota=None):
    return Bucket(
        name="team-bucket",
        path="unitacct/team-bucket",
        user_name="unitacct$user_1",
        quota=quota or SMALL_BUCKET_QUOTA.copy(),
    )


def make_update_schema(*, user=None, bucket=None):
    context = {}
    if user is not None:
        context["user"] = user
    if bucket is not None:
        context["bucket"] = bucket
    return BucketSchema(context=context)


def test_update_bucket_schema_accepts_without_context():
    loaded = BucketSchema(partial=True).load(
        {"quota": TYPICAL_BUCKET_QUOTA.copy()}
    )

    assert loaded["quota"] == TYPICAL_BUCKET_QUOTA


def test_update_bucket_schema_accepts_full_quota_update():
    schema = make_update_schema(
        user=make_s3_user(),
        bucket=make_bucket(),
    )

    loaded = schema.load({"quota": TYPICAL_BUCKET_QUOTA.copy()}, partial=True)

    assert loaded["quota"] == TYPICAL_BUCKET_QUOTA


def test_update_bucket_schema_accepts_partial_quota_update_and_preserves_current():
    schema = make_update_schema(
        user=make_s3_user(),
        bucket=make_bucket(quota={"data_size_mb": 2, "objects": 1}),
    )

    loaded = schema.load({"quota": {"objects": 2}}, partial=True)

    assert loaded["quota"] == {"data_size_mb": 2, "objects": 2}


def test_update_bucket_schema_accepts_unlimited_quota():
    schema = make_update_schema(
        user=make_s3_user(),
        bucket=make_bucket(),
    )

    loaded = schema.load({"quota": UNLIMITED_BUCKET_QUOTA.copy()}, partial=True)

    assert loaded["quota"] == UNLIMITED_BUCKET_QUOTA


@pytest.mark.parametrize(
    "quota, invalid_field",
    [
        ({"data_size_mb": -2}, "data_size_mb"),
        ({"objects": -2}, "objects"),
        ({"data_size_mb": "bad"}, "data_size_mb"),
        ({"objects": "bad"}, "objects"),
        ({"data_size_mb": 1, "objects": 1, "buckets": 1}, "quota"),
    ],
)
def test_update_bucket_schema_rejects_invalid_quota_values(quota, invalid_field):
    schema = make_update_schema(
        user=make_s3_user(),
        bucket=make_bucket(),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"quota": quota}, partial=True)

    if invalid_field == "quota":
        assert invalid_field in exc_info.value.messages
    else:
        assert invalid_field in exc_info.value.messages["quota"]


def test_update_bucket_schema_rejects_quota_above_user_quota():
    schema = make_update_schema(
        user=make_s3_user(data_size_mb=3, objects=3),
        bucket=make_bucket(),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"quota": {"data_size_mb": 4, "objects": 4}}, partial=True)

    assert exc_info.value.messages == {
        "data_size_mb": "Bucket quota 'data_size_mb' must not exceed user quota.",
        "objects": "Bucket quota 'objects' must not exceed user quota.",
    }
