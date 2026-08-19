import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_quota import IscsiQuotaUpdatePayload
from tests.schemes.iscsi_quota import IscsiQuotaResponseTestSchema


def validate_response(body):
    try:
        IscsiQuotaResponseTestSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"iSCSI quota response validation failed: {exc.messages}")


def make_update_quota_payload(**overrides):
    return IscsiQuotaUpdatePayload.build(
        clients=5,
        data_size_gb=25,
        disks=11,
        snapshots=7,
        **overrides,
    )


def assert_quota_updated(body, quota, payload):
    validate_response(body)
    assert body["id"] == quota.id
    assert body["clients"] == payload["clients"]
    assert body["data_size_gb"] == payload["data_size_gb"]
    assert body["disks"] == payload["disks"]
    assert body["snapshots"] == payload["snapshots"]


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_update_own_iscsi_quota(api, env, role):
    """Owner and admin can update iSCSI quota in their own account."""
    account = env.account()
    scope = env.scope(
        account=account,
        pool_name="nvme",
        clients=10,
        data_size_gb=100,
        disks=20,
        snapshots=30,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 200
    assert_quota_updated(body, scope.quota, payload)


def test_member_cannot_update_iscsi_quota(api, env):
    """Member has no permission to update iSCSI quotas."""
    account = env.account()
    scope = env.scope(
        account=account,
        pool_name="nvme",
        clients=10,
        data_size_gb=100,
        disks=20,
        snapshots=30,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=account.name, role="member")

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 403


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_update_iscsi_quota_in_other_account(api, env, role):
    """Owner/admin cannot update iSCSI quota belonging to another account."""
    quota_account, foreign_account = env.accounts(count=2)
    scope = env.scope(
        account=quota_account,
        pool_name="nvme",
        clients=10,
        data_size_gb=100,
        disks=20,
        snapshots=30,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 404


def test_operator_can_update_iscsi_quota_in_any_account(api, env):
    """Operator can update iSCSI quota in any account."""
    account = env.account()
    scope = env.scope(
        account=account,
        pool_name="nvme",
        clients=10,
        data_size_gb=100,
        disks=20,
        snapshots=30,
    )
    payload = make_update_quota_payload()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 200
    assert_quota_updated(body, scope.quota, payload)


def test_update_iscsi_quota_rejects_value_over_pool_limit(api, env):
    """iSCSI quota update cannot exceed default pool limitset."""
    account = env.account()
    scope = env.scope(
        account=account,
        pool_name="nvme",
        clients=10,
        data_size_gb=100,
        disks=20,
        snapshots=30,
    )
    payload = IscsiQuotaUpdatePayload.build(
        data_size_gb=scope.quota.get_limitset().data_size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 400
    assert "data_size_gb" in str(body)


def test_update_iscsi_quota_rejects_value_below_current_usage(api, env):
    """iSCSI quota update cannot be lower than current disk usage."""
    account = env.account()
    scope = env.scope(account=account, pool_name="nvme")
    disk = env.disk(target=scope.target, size_gb=6)
    payload = IscsiQuotaUpdatePayload.build(data_size_gb=disk.size_gb - 1)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.quotas.update(scope.quota.id, payload, headers)

    assert status == 400
    assert "data_size_gb" in str(body)


def test_update_nonexistent_iscsi_quota_returns_404(api):
    """Updating a nonexistent iSCSI quota returns 404."""
    headers = HeadersPayload.build(operator=True)

    payload = IscsiQuotaUpdatePayload.build(clients=1)

    status, body = api.iscsi.quotas.update(999999, payload, headers)

    assert status == 404
