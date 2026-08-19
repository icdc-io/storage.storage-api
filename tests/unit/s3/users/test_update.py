from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.s3_user import S3UserSchema, S3UserStatus
from tests.factories.s3_quota import S3QuotaFactory
from tests.factories.s3_user import (
    TYPICAL_USER_QUOTA,
    S3UserUpdatePayloadFactory,
)


def make_account_quota(
    *,
    data_size_mb=S3QuotaFactory.data_size_mb,
    objects=S3QuotaFactory.objects,
    buckets=S3QuotaFactory.buckets,
    users=S3QuotaFactory.users,
    usage_data_size_mb=0,
    usage_objects=0,
    usage_buckets=0,
    usage_users=0,
):
    return SimpleNamespace(
        data_size_mb=data_size_mb,
        objects=objects,
        buckets=buckets,
        users=users,
        compute_usage=lambda: {
            "data_size_mb": usage_data_size_mb,
            "objects": usage_objects,
            "buckets": usage_buckets,
            "users": usage_users,
        },
    )


def make_s3_user(
    *,
    data_size_mb=10,
    objects=5,
    buckets=1,
    usage_data_size_mb=0,
    usage_objects=0,
    usage_buckets=0,
):
    return SimpleNamespace(
        quota={
            "data_size_mb": data_size_mb,
            "objects": objects,
            "buckets": buckets,
        },
        usage={
            "data_size_mb": usage_data_size_mb,
            "objects": usage_objects,
            "buckets": usage_buckets,
        },
    )


def make_update_user_body(**overrides):
    body = S3UserUpdatePayloadFactory.build(
        owner="owner@example.com",
        description="updated description",
        quota=TYPICAL_USER_QUOTA.copy(),
    )
    body.update(overrides)
    return body


def make_update_schema(*, account_quota=None, user=None):
    context = {}
    if account_quota is not None:
        context["account_quota"] = account_quota
    if user is not None:
        context["user"] = user
    return S3UserSchema(context=context)


# Field validation


@pytest.mark.parametrize(
    "valid_email",
    [
        "owner@example.com",
        "test.user@domain.org",
        "test+tag@sub.domain.com",
    ],
)
def test_update_s3_user_schema_accepts_valid_owner_email(valid_email):
    loaded = S3UserSchema(partial=True).load(
        make_update_user_body(owner=valid_email)
    )

    assert loaded["owner"] == valid_email


@pytest.mark.parametrize(
    "invalid_email",
    [
        "owner",
        "owner@",
        "@example.com",
        "owner@example",
        "",
        None,
    ],
)
def test_update_s3_user_schema_rejects_invalid_owner_email(invalid_email):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema(partial=True).load(
            make_update_user_body(owner=invalid_email)
        )

    assert "owner" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_description",
    [
        "",
        "plain description",
        "desc: [ok] / yes!",
        "a" * 64,
    ],
)
def test_update_s3_user_schema_accepts_valid_description(valid_description):
    loaded = S3UserSchema(partial=True).load(
        make_update_user_body(description=valid_description)
    )

    assert loaded["description"] == valid_description


@pytest.mark.parametrize(
    "invalid_description",
    [
        "a" * 65,
        "bad|pipe",
        "bad\nnewline",
    ],
)
def test_update_s3_user_schema_rejects_invalid_description(invalid_description):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema(partial=True).load(
            make_update_user_body(description=invalid_description)
        )

    assert "description" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_status",
    [
        S3UserStatus.ACTIVE.value,
        S3UserStatus.LOCKED.value,
        S3UserStatus.DELETED.value,
        S3UserStatus.UNKNOWN.value,
    ],
)
def test_update_s3_user_schema_accepts_valid_status(valid_status):
    loaded = S3UserSchema(partial=True).load(
        make_update_user_body(status=valid_status)
    )

    assert loaded["status"] == valid_status


@pytest.mark.parametrize("invalid_status", ["paused", "", None])
def test_update_s3_user_schema_rejects_invalid_status(invalid_status):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema(partial=True).load(
            make_update_user_body(status=invalid_status)
        )

    assert "status" in exc_info.value.messages


def test_update_s3_user_schema_accepts_empty_payload():
    loaded = S3UserSchema(partial=True).load({})

    assert loaded == {}


def test_update_s3_user_schema_accepts_valid_owner_and_description_together():
    loaded = S3UserSchema(partial=True).load(
        make_update_user_body(
            owner="mixed@example.com",
            description="mixed description",
            status=S3UserStatus.LOCKED.value,
        )
    )

    assert loaded == {
        "owner": "mixed@example.com",
        "description": "mixed description",
        "status": S3UserStatus.LOCKED.value,
        "quota": TYPICAL_USER_QUOTA,
    }


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_update_s3_user_schema_rejects_unknown_field(unknown_field):
    payload = make_update_user_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema(partial=True).load(payload)

    assert unknown_field in exc_info.value.messages


# Quota validation


def test_update_s3_user_schema_accepts_without_account_quota_context():
    loaded = S3UserSchema(partial=True).load(
        make_update_user_body(quota={"data_size_mb": 12, "objects": 6, "buckets": 2})
    )

    assert loaded["quota"] == {"data_size_mb": 12, "objects": 6, "buckets": 2}


def test_update_s3_user_schema_accepts_owner_only_with_quota_and_user_context():
    schema = make_update_schema(
        account_quota=make_account_quota(),
        user=make_s3_user(),
    )

    loaded = schema.load({"owner": "quota-owner@example.com"}, partial=True)

    assert loaded == {"owner": "quota-owner@example.com"}


def test_update_s3_user_schema_accepts_valid_quota():
    schema = make_update_schema(
        account_quota=make_account_quota(),
        user=make_s3_user(),
    )
    quota = {"data_size_mb": 12, "objects": 6, "buckets": 2}

    loaded = schema.load({"quota": quota}, partial=True)

    assert loaded["quota"] == quota


def test_update_s3_user_schema_accepts_partial_quota_update():
    schema = make_update_schema(
        account_quota=make_account_quota(),
        user=make_s3_user(),
    )

    loaded = schema.load({"quota": {"objects": 6}}, partial=True)

    assert loaded["quota"] == {"objects": 6}


@pytest.mark.parametrize(
    "quota, invalid_field",
    [
        ({"data_size_mb": -1, "objects": 5, "buckets": 1}, "data_size_mb"),
        ({"data_size_mb": 10, "objects": -1, "buckets": 1}, "objects"),
        ({"data_size_mb": 10, "objects": 5, "buckets": -1}, "buckets"),
        ({"data_size_mb": "bad", "objects": 5, "buckets": 1}, "data_size_mb"),
        ({"data_size_mb": 10, "objects": "bad", "buckets": 1}, "objects"),
        ({"data_size_mb": 10, "objects": 5, "buckets": "bad"}, "buckets"),
    ],
)
def test_update_s3_user_schema_rejects_invalid_quota_values(quota, invalid_field):
    schema = make_update_schema(
        account_quota=make_account_quota(),
        user=make_s3_user(),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"quota": quota}, partial=True)

    assert invalid_field in exc_info.value.messages


def test_update_s3_user_schema_accepts_quota_at_account_boundary():
    schema = make_update_schema(
        account_quota=make_account_quota(
            data_size_mb=30,
            objects=20,
            buckets=3,
            usage_data_size_mb=20,
            usage_objects=15,
            usage_buckets=2,
        ),
        user=make_s3_user(
            data_size_mb=10,
            objects=5,
            buckets=1,
        ),
    )

    loaded = schema.load(
        {"quota": {"data_size_mb": 10, "objects": 5, "buckets": 1}},
        partial=True,
    )

    assert loaded["quota"] == {"data_size_mb": 10, "objects": 5, "buckets": 1}


def test_update_s3_user_schema_rejects_quota_over_account_limit():
    schema = make_update_schema(
        account_quota=make_account_quota(
            data_size_mb=25,
            objects=20,
            buckets=3,
            usage_data_size_mb=20,
            usage_objects=10,
            usage_buckets=2,
        ),
        user=make_s3_user(
            data_size_mb=10,
            objects=5,
            buckets=1,
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(
            {"quota": {"data_size_mb": 16, "objects": 5, "buckets": 1}},
            partial=True,
        )

    assert exc_info.value.messages == {
        "data_size_mb": "Overflow of account quota on data_size_mb: 26/25",
    }


@pytest.mark.parametrize(
    "field, account_limit, current_value, requested_value",
    [
        ("data_size_mb", 20, 30, 25),
        ("objects", 20, 30, 25),
        ("buckets", 2, 5, 3),
    ],
)
def test_update_s3_user_schema_rejects_quota_value_over_account_quota(
    field,
    account_limit,
    current_value,
    requested_value,
):
    account_quota_kwargs = {
        "data_size_mb": 100,
        "objects": 100,
        "buckets": 100,
        "usage_data_size_mb": 10,
        "usage_objects": 10,
        "usage_buckets": 1,
    }
    user_kwargs = {
        "data_size_mb": 10,
        "objects": 5,
        "buckets": 1,
    }
    account_quota_kwargs[field] = account_limit
    user_kwargs[field] = current_value
    schema = make_update_schema(
        account_quota=make_account_quota(**account_quota_kwargs),
        user=make_s3_user(**user_kwargs),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load({"quota": {field: requested_value}}, partial=True)

    assert exc_info.value.messages == {
        field: f"S3User quota '{field}' must not exceed account quota.",
    }


def test_update_s3_user_schema_rejects_quota_below_current_usage():
    schema = make_update_schema(
        account_quota=make_account_quota(),
        user=make_s3_user(
            data_size_mb=10,
            objects=5,
            buckets=1,
            usage_data_size_mb=8,
            usage_objects=4,
            usage_buckets=1,
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(
            {"quota": {"data_size_mb": 7, "objects": 3, "buckets": 0}},
            partial=True,
        )

    assert exc_info.value.messages == {
        "data_size_mb": "Requested S3 user quota 7 can not be less than current usage: 8",
        "objects": "Requested S3 user quota 3 can not be less than current usage: 4",
        "buckets": "Requested S3 user quota 0 can not be less than current usage: 1",
    }
