import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskUpdatePayload


def test_member_can_update_own_disk(api, env):
    """Member can resize their own iSCSI disk."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    payload = IscsiDiskUpdatePayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=disk_ctx.account.name,
        role="member",
        user=disk_ctx.disk.owner,
    )

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["size_gb"] == payload["size_gb"]
    assert disk_ctx.disk.size_gb == payload["size_gb"]


def test_member_cannot_update_non_own_disk(api, env):
    """Member cannot update a disk owned by another user in the same account."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_size_gb = disk_ctx.disk.size_gb
    payload = IscsiDiskUpdatePayload.build(size_gb=3)
    headers = HeadersPayload.build(
        account=disk_ctx.account.name,
        role="member",
        user="other_user@example.com",
    )

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 404, "Disk not found."
    assert disk_ctx.disk.size_gb == old_size_gb


def test_member_cannot_change_owner_of_own_disk(api, env):
    """Member cannot change the owner of their own disk."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_owner = disk_ctx.disk.owner
    payload = IscsiDiskUpdatePayload.build(changed_owner=True)
    headers = HeadersPayload.build(
        account=disk_ctx.account.name,
        role="member",
        user=disk_ctx.disk.owner,
    )

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["owner"] == old_owner
    assert disk_ctx.disk.owner == old_owner


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_update_account_disk(api, env, role):
    """Admin and owner can resize disks in their own account."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    payload = IscsiDiskUpdatePayload.build(size_gb=3)
    headers = HeadersPayload.build(account=disk_ctx.account.name, role=role)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["size_gb"] == payload["size_gb"]
    assert disk_ctx.disk.size_gb == payload["size_gb"]


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_update_disk_in_other_account(api, env, role):
    """Non-operator roles cannot update a disk in another account."""
    owner_disk_ctx = env.disk_scope(pool_name="nvme")
    foreign_account = env.account()
    old_owner = owner_disk_ctx.disk.owner
    payload = IscsiDiskUpdatePayload.build(changed_owner=True)
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=owner_disk_ctx.disk.owner,
    )

    status, body = api.iscsi.disks.update(owner_disk_ctx.disk.id, payload, headers)

    assert status == 404, "Disk not found."
    assert owner_disk_ctx.disk.owner == old_owner


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_change_disk_owner(api, env, role):
    """Admin and owner can change disk owner inside their own account."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_owner = disk_ctx.disk.owner
    payload = IscsiDiskUpdatePayload.build(changed_owner=True)
    headers = HeadersPayload.build(account=disk_ctx.account.name, role=role)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["owner"] == payload["owner"]
    assert body["owner"] != old_owner
    assert disk_ctx.disk.owner == payload["owner"]


def test_operator_can_update_disk_in_any_account(api, env):
    """Operator can resize any disk across accounts."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    payload = IscsiDiskUpdatePayload.build(size_gb=3)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["size_gb"] == payload["size_gb"]
    assert disk_ctx.disk.size_gb == payload["size_gb"]


def test_operator_can_change_disk_owner(api, env):
    """Operator can change disk owner across accounts."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_owner = disk_ctx.disk.owner
    payload = IscsiDiskUpdatePayload.build(changed_owner=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["owner"] == payload["owner"]
    assert body["owner"] != old_owner
    assert disk_ctx.disk.owner == payload["owner"]


def test_operator_can_update_disk_owner_and_size_together(
    api,
    env,
    mocked_iscsi_service,
):
    """Operator can update owner and resize in one request."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_owner = disk_ctx.disk.owner
    payload = IscsiDiskUpdatePayload.build(
        changed_owner=True,
        size_gb=disk_ctx.disk.size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["owner"] == payload["owner"]
    assert body["owner"] != old_owner
    assert body["size_gb"] == payload["size_gb"]
    assert disk_ctx.disk.owner == payload["owner"]
    assert disk_ctx.disk.size_gb == payload["size_gb"]
    mocked_iscsi_service.update_disk.assert_called_once_with(
        disk_ctx.disk.name,
        payload,
    )


def test_owner_only_update_does_not_call_ceph_resize(api, env, mocked_iscsi_service):
    """Changing only owner is a DB update and should not call Ceph resize."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    payload = IscsiDiskUpdatePayload.build(changed_owner=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["owner"] == payload["owner"]
    mocked_iscsi_service.update_disk.assert_not_called()


def test_update_same_size_does_not_call_ceph_resize(api, env, mocked_iscsi_service):
    """Updating with the current size is accepted as a no-op."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    payload = IscsiDiskUpdatePayload.build(size_gb=disk_ctx.disk.size_gb)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 200
    assert body["size_gb"] == disk_ctx.disk.size_gb
    mocked_iscsi_service.update_disk.assert_not_called()


def test_update_disk_rejects_resize_over_quota(api, env, mocked_iscsi_service):
    """Resize is rejected before Ceph call when quota would overflow."""
    scope_ctx = env.scope(pool_name="nvme", data_size_gb=1, disks=10)
    disk = env.disk(target=scope_ctx.target, size_gb=1)
    payload = IscsiDiskUpdatePayload.build(size_gb=2)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk.id, payload, headers)

    assert status == 400
    assert "size_gb" in str(body)
    mocked_iscsi_service.update_disk.assert_not_called()


def test_update_disk_returns_ceph_service_error(api, env, mocked_iscsi_service):
    """Ceph resize failure is returned and DB size is not changed."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    old_size_gb = disk_ctx.disk.size_gb
    mocked_iscsi_service.update_disk.return_value = {
        "code": 500,
        "data": "ceph resize failed",
    }
    payload = IscsiDiskUpdatePayload.build(size_gb=old_size_gb + 1)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk_ctx.disk.id, payload, headers)

    assert status == 500
    assert disk_ctx.disk.size_gb == old_size_gb


def test_update_nonexistent_disk_returns_404(api):
    """Updating a nonexistent disk returns 404."""
    payload = IscsiDiskUpdatePayload.build()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(99999, payload, headers)

    assert status == 404, "Disk not found."
