import pytest

from app.models.iscsi_quota import IscsiQuotas
from app.models.iscsi_target import IscsiTargets
from tests.factories.headers import HeadersPayload


def assert_quota_deleted(quota):
    assert IscsiQuotas.query.filter_by(id=quota.id).first() is None


def assert_quota_exists(quota):
    assert IscsiQuotas.query.filter_by(id=quota.id).first() is not None


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_delete_own_iscsi_quota(api, env, role):
    """Owner and admin can delete iSCSI quota in their own account."""
    account = env.account()
    quota = env.quota(account=account)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.quotas.delete(quota.id, headers)

    assert status == 204
    assert_quota_deleted(quota)


def test_member_cannot_delete_iscsi_quota(api, env):
    """Member has no permission to delete iSCSI quotas."""
    account = env.account()
    quota = env.quota(account=account)
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.iscsi.quotas.delete(quota.id, headers)

    assert status == 403
    assert_quota_exists(quota)


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_delete_iscsi_quota_in_other_account(api, env, role):
    """Owner/admin cannot delete iSCSI quota belonging to another account."""
    quota_account, foreign_account = env.accounts(count=2)
    quota = env.quota(account=quota_account)
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.iscsi.quotas.delete(quota.id, headers)

    assert status == 404
    assert_quota_exists(quota)


def test_operator_can_delete_iscsi_quota_in_any_account(api, env):
    """Operator can delete iSCSI quota in any account."""
    account = env.account()
    quota = env.quota(account=account)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.delete(quota.id, headers)

    assert status == 204
    assert_quota_deleted(quota)


def test_delete_iscsi_quota_with_target_deletes_target(api, env):
    """Deleting an iSCSI quota also removes the related target for that pool."""
    account = env.account()
    scope = env.scope(account=account)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.delete(scope.quota.id, headers)

    assert status == 204
    assert_quota_deleted(scope.quota)
    assert IscsiTargets.query.filter_by(id=scope.target.id).first() is None


def test_delete_nonexistent_iscsi_quota_returns_404(api):
    """Deleting a nonexistent iSCSI quota returns 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.delete(999999, headers)

    assert status == 404
