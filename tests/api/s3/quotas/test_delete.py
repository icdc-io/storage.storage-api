import pytest

from app.models.s3_quota import S3Quotas
from tests.factories.headers import HeadersPayload


def assert_quota_deleted(quota):
    assert S3Quotas.query.filter_by(id=quota.id).first() is None


def assert_quota_exists(quota):
    assert S3Quotas.query.filter_by(id=quota.id).first() is not None


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_delete_own_s3_quota(api, env, role):
    """Owner and admin can delete S3 quota in their own account."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
    )
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.s3.quotas.delete(quota.id, headers)

    assert status == 204
    assert_quota_deleted(quota)


def test_member_cannot_delete_s3_quota(api, env):
    """Member has no permission to delete S3 quotas."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
    )
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.s3.quotas.delete(quota.id, headers)

    assert status == 403
    assert_quota_exists(quota)


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_delete_s3_quota_in_other_account(api, env, role):
    """Owner/admin cannot delete S3 quota belonging to another account."""
    quota_account, foreign_account = env.accounts(count=2)
    quota = env.quota(
        account=quota_account,
        pool_name="nvme",
    )
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.s3.quotas.delete(quota.id, headers)

    assert status == 404
    assert_quota_exists(quota)


def test_operator_can_delete_s3_quota_in_any_account(api, env):
    """Operator can delete S3 quota in any account."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.delete(quota.id, headers)

    assert status == 204
    assert_quota_deleted(quota)


def test_delete_s3_quota_with_existing_user_returns_409(api, env):
    """S3 quota cannot be deleted while S3 users exist for that pool."""
    account = env.account()
    quota = env.quota(
        account=account,
        pool_name="nvme",
    )
    env.user(account=account, pool_name="nvme")
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.delete(quota.id, headers)

    assert status == 409
    assert_quota_exists(quota)


def test_delete_nonexistent_s3_quota_returns_404(api):
    """Deleting a nonexistent S3 quota returns 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.quotas.delete(999999, headers)

    assert status == 404
