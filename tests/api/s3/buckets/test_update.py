import pytest

from tests.builders.s3_namespace import BucketContext
from tests.factories.bucket import SMALL_BUCKET_QUOTA, UNLIMITED_BUCKET_QUOTA
from tests.factories.headers import HeadersPayload


def test_member_can_update_own_bucket(api, env):
    """Member can update a bucket owned by their own S3 user."""
    bucket_ctx = env.bucket_scope()
    payload = {"quota": SMALL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(
        account=bucket_ctx.account.name,
        role="member",
        user=bucket_ctx.user.owner,
    )

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == payload["quota"]


def test_member_cannot_update_other_member_bucket(api, env):
    """Member cannot update a bucket owned by another user in the same account."""
    bucket_ctx = env.bucket_scope()
    payload = {"quota": SMALL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(
        account=bucket_ctx.account.name,
        role="member",
        user="other_user@example.com",
    )

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 401
    assert body["message"] == "You haven't permission for this bucket."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_update_bucket_in_own_account(
    api,
    env,
    role,
):
    """Admin and owner can update buckets in their own account."""
    bucket_ctx = env.bucket_scope()
    payload = {"quota": SMALL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(account=bucket_ctx.account.name, role=role)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == payload["quota"]


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_non_operator_roles_cannot_update_bucket_in_other_account(
    api,
    env,
    role,
):
    """Non-operator roles cannot update buckets in another account."""
    bucket_ctx = env.bucket_scope()
    foreign_account = env.account()
    payload = {"quota": SMALL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=bucket_ctx.user.owner,
    )

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 401
    assert body["message"] == "You haven't permission for this bucket."


def test_operator_can_update_bucket_in_any_account(api, env):
    """Operator can update a bucket in any account."""
    bucket_ctx = env.bucket_scope()
    payload = {"quota": SMALL_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == payload["quota"]


def test_operator_can_update_bucket_to_unlimited_quota(api, env):
    bucket_ctx = env.bucket_scope()
    payload = {"quota": UNLIMITED_BUCKET_QUOTA.copy()}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 200
    assert body["quota"] == UNLIMITED_BUCKET_QUOTA


def test_update_bucket_rejects_quota_over_user_limit(api, env):
    """Bucket quota cannot exceed the parent S3 user quota."""
    user_ctx = env.user_scope(
        quota={"data_size_mb": 3, "objects": 3, "buckets": 3},
    )
    bucket = env.bucket(s3_user=user_ctx.user)
    bucket_ctx = BucketContext(
        account=user_ctx.account,
        quota=user_ctx.quota,
        pool_name=user_ctx.pool_name,
        user=user_ctx.user,
        bucket=bucket,
    )
    payload = {"quota": {"data_size_mb": 4, "objects": 4}}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, payload, headers)

    assert status == 400
    assert body["message"] == "Invalid parameters!"
    assert body["errors"] == [
        "data_size_mb: Bucket quota 'data_size_mb' must not exceed user quota.",
        "objects: Bucket quota 'objects' must not exceed user quota.",
    ]


def test_update_bucket_without_quota_returns_404(api, env):
    """Bucket update requires the quota field."""
    bucket_ctx = env.bucket_scope()
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update(bucket_ctx.bucket.path, {}, headers)

    assert status == 404
    assert body["message"] == "Missed parameter 'quota'."


def test_update_nonexistent_bucket_returns_404(api):
    """Updating an unknown bucket path returns 404."""
    payload = {"quota": {"data_size_mb": 2, "objects": 2}}
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.update("aqa/missing-bucket", payload, headers)

    assert status == 404
    assert body["message"] == "Bucket with this name not found."
