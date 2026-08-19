import pytest

from app.models.iscsi_disk import IscsiDisks
from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskCreatePayload


def test_create_disk_with_real_db_state(api, env, mocked_iscsi_service):
    scope_ctx = env.scope(pool_name="nvme")

    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
        owner="user@example.com",
        size_gb=2,
        name="disk01",
    )
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert body["owner"] == payload["owner"]
    assert body["size_gb"] == payload["size_gb"]
    assert body["name"] == payload["name"]

    disk = IscsiDisks.query.filter_by(id=body["id"]).first()
    assert disk is not None
    assert disk.target_id == scope_ctx.target.id
    assert disk.owner == payload["owner"]
    assert disk.size_gb == payload["size_gb"]
    assert disk.name == payload["name"]
    mocked_iscsi_service.create_disk.assert_called_once_with(
        body={
            "owner": payload["owner"],
            "size_gb": payload["size_gb"],
            "name": payload["name"],
            "target_id": scope_ctx.target.id,
        }
    )


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_can_create_disk_in_own_account(
    api,
    env,
    role,
):
    """Owner, admin, and member can create a disk in their own account."""
    scope_ctx = env.scope(pool_name="nvme")

    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
    )
    headers = HeadersPayload.build(account=scope_ctx.account.name, role=role)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201, 204)


def test_operator_can_create_disk_in_any_account(
    api,
    env,
):
    """Operator can create a disk for another account using the devel account."""
    scope_ctx = env.scope(pool_name="nvme")

    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201, 204)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_cannot_create_disk_in_other_account(
    api,
    env,
    role,
    mocked_iscsi_service,
):
    """Account-scoped roles cannot create a disk for a foreign account."""
    scope_ctx = env.scope(pool_name="nvme")
    foreign_account = env.account()
    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
    )
    headers = HeadersPayload.build(account=foreign_account.name, role=role)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status == 404
    mocked_iscsi_service.create_disk.assert_not_called()


def test_create_disk_uses_subject_account_when_payload_has_no_account_name(
    api,
    env,
):
    """If account_name is omitted, the authenticated subject account is used."""
    scope_ctx = env.scope(pool_name="nvme")
    payload = IscsiDiskCreatePayload.build(
        pool_id=scope_ctx.quota.pool_id,
    )
    headers = HeadersPayload.build(account=scope_ctx.account.name, role="member")

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201)
    disk = IscsiDisks.query.filter_by(id=body["id"]).first()
    assert disk.target_id == scope_ctx.target.id


def test_create_disk_rejects_missing_target_for_pool(api, env, mocked_iscsi_service):
    """Disk create fails when the account has no target for the requested pool."""
    account = env.account()
    payload = IscsiDiskCreatePayload.build(
        account_name=account.name,
        pool_id=999999,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status == 404
    mocked_iscsi_service.create_disk.assert_not_called()


def test_create_disk_rejects_size_over_quota(api, env, mocked_iscsi_service):
    """Disk create is rejected before Ceph call when quota would overflow."""
    scope_ctx = env.scope(pool_name="nvme", data_size_gb=1, disks=10)
    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
        size_gb=2,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status == 400
    assert "size_gb" in str(body)
    mocked_iscsi_service.create_disk.assert_not_called()


def test_create_disk_returns_ceph_service_error(api, env, mocked_iscsi_service):
    """Ceph create failure is returned and disk is not stored in DB."""
    scope_ctx = env.scope(pool_name="nvme")
    mocked_iscsi_service.create_disk.return_value = {
        "code": 500,
        "data": "ceph create failed",
    }
    payload = IscsiDiskCreatePayload.build(
        account_name=scope_ctx.account.name,
        pool_id=scope_ctx.quota.pool_id,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status == 500
    assert IscsiDisks.query.filter_by(name=payload["name"]).first() is None
