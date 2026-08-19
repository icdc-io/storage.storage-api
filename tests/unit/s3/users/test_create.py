from types import SimpleNamespace

import pytest
from marshmallow import ValidationError

from app.models.s3_user import S3UserSchema
from tests.factories.s3_quota import S3QuotaFactory
from tests.factories.s3_user import (
    ACTIVE_USER_QUOTA,
    TYPICAL_USER_QUOTA,
    S3UserCreatePayloadFactory,
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


def make_create_user_body(**overrides):
    body = S3UserCreatePayloadFactory.build(
        typical_quota=True,
        name="unitacct$user_1",
        account_id=1,
        pool_id=2,
    )
    body.update(overrides)
    return body


def make_create_schema(*, account_quota=None):
    if account_quota is None:
        return S3UserSchema()
    return S3UserSchema(context={"account_quota": account_quota})


# Field validation


@pytest.mark.parametrize(
    "valid_name",
    [
        "unitacct$user_1",
        "unitacct$user.name-1",
        "unitacct$user@example.com",
        "user_1",
        "a" * 89,
    ],
)
def test_s3_user_schema_accepts_valid_name(valid_name):
    loaded = S3UserSchema().load(make_create_user_body(name=valid_name))

    assert loaded["name"] == valid_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "unitacct$User_1",
        "unitacct$user/slash",
        "unitacct$user space",
        "",
        None,
        "a" * 90,
    ],
)
def test_s3_user_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(make_create_user_body(name=invalid_name))

    assert "name" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_email",
    [
        "owner@example.com",
        "test.user@domain.org",
        "test+tag@sub.domain.com",
    ],
)
def test_s3_user_schema_accepts_valid_owner_email(valid_email):
    loaded = S3UserSchema().load(make_create_user_body(owner=valid_email))

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
def test_s3_user_schema_rejects_invalid_owner_email(invalid_email):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(make_create_user_body(owner=invalid_email))

    assert "owner" in exc_info.value.messages


@pytest.mark.parametrize("valid_account_id", [1, 2, 999])
def test_s3_user_schema_accepts_valid_account_id(valid_account_id):
    loaded = S3UserSchema().load(
        make_create_user_body(account_id=valid_account_id)
    )

    assert loaded["account_id"] == valid_account_id


@pytest.mark.parametrize("invalid_account_id", ["bad", None])
def test_s3_user_schema_rejects_invalid_account_id(invalid_account_id):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(
            make_create_user_body(account_id=invalid_account_id)
        )

    assert "account_id" in exc_info.value.messages


@pytest.mark.parametrize("valid_pool_id", [1, 2, 999])
def test_s3_user_schema_accepts_valid_pool_id(valid_pool_id):
    loaded = S3UserSchema().load(make_create_user_body(pool_id=valid_pool_id))

    assert loaded["pool_id"] == valid_pool_id


@pytest.mark.parametrize("invalid_pool_id", ["bad", None])
def test_s3_user_schema_rejects_invalid_pool_id(invalid_pool_id):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(make_create_user_body(pool_id=invalid_pool_id))

    assert "pool_id" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_description",
    [
        "",
        "plain description",
        "desc: [ok] / yes!",
        "a" * 64,
    ],
)
def test_s3_user_schema_accepts_valid_description(valid_description):
    loaded = S3UserSchema().load(
        make_create_user_body(description=valid_description)
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
def test_s3_user_schema_rejects_invalid_description(invalid_description):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(
            make_create_user_body(description=invalid_description)
        )

    assert "description" in exc_info.value.messages


@pytest.mark.parametrize(
    "missing_field",
    ["name", "owner", "account_id", "pool_id", "quota"],
)
def test_s3_user_schema_rejects_missing_required_field(missing_field):
    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(make_create_user_body(**{missing_field: None}))

    assert missing_field in exc_info.value.messages


@pytest.mark.parametrize("unknown_field", ["extra_field", "unrelated", "random_key"])
def test_s3_user_schema_rejects_unknown_field(unknown_field):
    payload = make_create_user_body()
    payload[unknown_field] = "error"

    with pytest.raises(ValidationError) as exc_info:
        S3UserSchema().load(payload)

    assert unknown_field in exc_info.value.messages


# Quota validation


def test_s3_user_schema_accepts_create_without_account_quota_context():
    loaded = S3UserSchema().load(make_create_user_body())

    assert loaded["quota"] == TYPICAL_USER_QUOTA


def test_s3_user_schema_accepts_valid_quota():
    schema = make_create_schema(account_quota=make_account_quota())
    quota = TYPICAL_USER_QUOTA.copy()

    loaded = schema.load(make_create_user_body(quota=quota))

    assert loaded["quota"] == quota


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
def test_s3_user_schema_rejects_invalid_quota_values(quota, invalid_field):
    schema = make_create_schema(account_quota=make_account_quota())

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_create_user_body(quota=quota))

    assert invalid_field in exc_info.value.messages


def test_s3_user_schema_accepts_quota_at_account_boundary():
    schema = make_create_schema(
        account_quota=make_account_quota(
            data_size_mb=30,
            objects=20,
            buckets=3,
            users=2,
            usage_data_size_mb=20,
            usage_objects=15,
            usage_buckets=2,
            usage_users=1,
        )
    )

    loaded = schema.load(
        make_create_user_body(
            quota=ACTIVE_USER_QUOTA.copy()
        )
    )

    assert loaded["quota"] == ACTIVE_USER_QUOTA


def test_s3_user_schema_accepts_user_count_at_account_boundary():
    schema = make_create_schema(
        account_quota=make_account_quota(
            users=1,
            usage_users=0,
        )
    )

    loaded = schema.load(make_create_user_body())

    assert loaded["quota"] == TYPICAL_USER_QUOTA


def test_s3_user_schema_rejects_quota_over_account_limit():
    schema = make_create_schema(
        account_quota=make_account_quota(
            data_size_mb=25,
            objects=20,
            buckets=3,
            users=1,
            usage_data_size_mb=25,
            usage_objects=10,
            usage_buckets=2,
            usage_users=1,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(
            make_create_user_body(
                quota=ACTIVE_USER_QUOTA.copy()
            )
        )

    assert exc_info.value.messages == {
        "data_size_mb": "Overflow of account quota on data_size_mb: 26/25",
        "users": "Overflow of account quota on users",
    }


@pytest.mark.parametrize(
    "field, account_limit, account_usage, requested_value",
    [
        ("data_size_mb", 25, 20, 10),
        ("objects", 14, 10, 5),
        ("buckets", 2, 2, 1),
    ],
)
def test_s3_user_schema_rejects_create_when_account_quota_usage_overflows(
    field,
    account_limit,
    account_usage,
    requested_value,
):
    account_quota_kwargs = {
        "data_size_mb": 100,
        "objects": 100,
        "buckets": 100,
        "users": 10,
        "usage_data_size_mb": 0,
        "usage_objects": 0,
        "usage_buckets": 0,
        "usage_users": 0,
    }
    usage_key = f"usage_{field}"
    account_quota_kwargs[field] = account_limit
    account_quota_kwargs[usage_key] = account_usage
    schema = make_create_schema(account_quota=make_account_quota(**account_quota_kwargs))

    quota = TYPICAL_USER_QUOTA.copy()
    quota[field] = requested_value

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_create_user_body(quota=quota))

    assert exc_info.value.messages == {
        field: (
            f"Overflow of account quota on {field}: "
            f"{account_usage + requested_value}/{account_limit}"
        ),
    }


@pytest.mark.parametrize(
    "field, account_limit, account_usage, requested_value",
    [
        ("data_size_mb", 30, 20, 10),
        ("objects", 15, 10, 5),
        ("buckets", 3, 2, 1),
    ],
)
def test_s3_user_schema_accepts_create_when_account_quota_usage_fits(
    field,
    account_limit,
    account_usage,
    requested_value,
):
    account_quota_kwargs = {
        "data_size_mb": 100,
        "objects": 100,
        "buckets": 100,
        "users": 10,
        "usage_data_size_mb": 0,
        "usage_objects": 0,
        "usage_buckets": 0,
        "usage_users": 0,
    }
    usage_key = f"usage_{field}"
    account_quota_kwargs[field] = account_limit
    account_quota_kwargs[usage_key] = account_usage
    schema = make_create_schema(account_quota=make_account_quota(**account_quota_kwargs))

    quota = TYPICAL_USER_QUOTA.copy()
    quota[field] = requested_value

    loaded = schema.load(make_create_user_body(quota=quota))

    assert loaded["quota"] == quota


def test_s3_user_schema_rejects_create_when_user_count_quota_is_reached():
    schema = make_create_schema(
        account_quota=make_account_quota(
            users=1,
            usage_users=1,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        schema.load(make_create_user_body())

    assert exc_info.value.messages == {
        "users": "Overflow of account quota on users",
    }
