import pytest

from tests.factories.bucket import (
    SMALL_BUCKET_QUOTA,
    UNLIMITED_BUCKET_QUOTA,
    BucketCreatePayloadFactory,
)
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import ACTIVE_USER_QUOTA
from tests.schemes.bucket import BucketResponseTestSchema
from tests.support.assertions import assert_schema_response


def assert_valid_bucket_response(body):
    assert_schema_response(
        body,
        BucketResponseTestSchema,
        message="Bucket response validation failed",
    )


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_can_create_bucket_in_own_account(
    api,
    env,
    role,
):
    """Owner, admin, and member can create a bucket in their own account."""
    user_ctx = env.user_scope(pool_name="nvme")

    payload = BucketCreatePayloadFactory.build(
        user_name=user_ctx.user.name,
        quota=SMALL_BUCKET_QUOTA.copy(),
    )
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role=role,
        user=user_ctx.user.owner,
    )

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_bucket_response(body)
    assert body["user_name"] == user_ctx.user.name
    assert body["quota"] == payload["quota"]


def test_operator_can_create_bucket_in_any_account(
    api,
    env,
):
    """Operator can create a bucket for another account using the devel account."""
    user_ctx = env.user_scope(pool_name="nvme")

    payload = BucketCreatePayloadFactory.build(
        user_name=user_ctx.user.name,
        quota=SMALL_BUCKET_QUOTA.copy(),
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_bucket_response(body)
    assert body["user_name"] == user_ctx.user.name


def test_create_bucket_applies_unlimited_quota(api, env):
    user_ctx = env.user_scope(pool_name="nvme")
    payload = BucketCreatePayloadFactory.build(
        user_name=user_ctx.user.name,
        quota=UNLIMITED_BUCKET_QUOTA.copy(),
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 201
    assert_valid_bucket_response(body)
    assert body["quota"] == UNLIMITED_BUCKET_QUOTA


def test_member_cannot_create_bucket_for_other_user(api, env):
    user_ctx = env.user_scope(pool_name="nvme", owner="bucket-owner@example.com")
    payload = BucketCreatePayloadFactory.build(user_name=user_ctx.user.name)
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user="other-user@example.com",
    )

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 404
    assert body["message"] == "User with this name not found or you haven't permission for it."


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_cannot_create_bucket_in_foreign_account(api, env, role):
    own_account, foreign_account = env.accounts(count=2)
    user_ctx = env.user_scope(account=foreign_account)
    payload = BucketCreatePayloadFactory.build(user_name=user_ctx.user.name)
    headers = HeadersPayload.build(
        account=own_account.name,
        role=role,
        user=user_ctx.user.owner,
    )

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 404
    assert body["message"] == "User with this name not found or you haven't permission for it."


def test_create_bucket_rejects_quota_over_user_limit(api, env):
    user_ctx = env.user_scope(quota=ACTIVE_USER_QUOTA.copy())
    payload = BucketCreatePayloadFactory.build(
        user_name=user_ctx.user.name,
        quota={"data_size_mb": 10, "objects": 10},
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.create(payload=payload, header=headers)

    assert status == 400
    assert body["message"] == "Invalid parameters"
    assert body["errors"] == [
        "data_size_mb: Bucket quota 'data_size_mb' must not exceed user quota.",
        "objects: Bucket quota 'objects' must not exceed user quota.",
    ]
