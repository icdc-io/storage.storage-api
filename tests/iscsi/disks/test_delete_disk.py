import pytest

from tests.factories.headers import HeadersPayload


def test_member_can_delete_own_disk(api, account, disk_db):
    """Member can delete their own iSCSI disk."""
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk_db.owner,
    )

    status, body = api.iscsi.disks.delete(disk_db.id, headers)

    assert status == 204


def test_member_cannot_delete_non_own_disk(api, account, disk_db):
    """Member cannot delete a disk they do not own."""
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        fake_user=True,
    )

    status, body = api.iscsi.disks.delete(disk_db.id, headers)

    assert status == 404, "Disk not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_or_owner_can_delete_disk_in_own_account(
    api,
    account,
    disk_db,
    role,
):
    """Admin/Owner can delete disks in their own account."""
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.disks.delete(disk_db.id, headers)

    assert status == 204


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_delete_disk_in_other_account(
    api,
    account_factory,
    disk_db,
    role,
):
    """Non-operator roles cannot delete disk in another account."""
    account = account_factory(count=1)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=disk_db.owner,
    )

    status, body = api.iscsi.disks.delete(disk_db.id, headers)

    assert status == 404, "Disk not found."


def test_operator_can_delete_disk_in_any_account(api, account, disk_db):
    """Operator can delete disk in any account."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk_db.id, headers)

    assert status == 204


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_operator_can_delete_ceph_disk_in_each_pool(
    api,
    disk_ceph_factory,
    pool_name,
):
    """Operator can delete Ceph-backed disk in any pool."""
    disk = disk_ceph_factory(disk_pools=pool_name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk.id, headers)

    assert status == 204


def test_delete_nonexistent_disk_returns_404(api):
    """Deleting non-existent disk should return 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(99999, headers)

    assert status == 404, "Disk not found."


def test_cannot_delete_assigned_disk_until_unassigned(
    api,
    client_db_assigned,
    db_unassign_client,
):
    """Deleting assigned disk returns 409, then succeeds after unassign."""
    disk = client_db_assigned.disks[0]
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk.id, headers)
    assert status == 409

    db_unassign_client(client_db_assigned)

    status, body = api.iscsi.disks.delete(disk.id, headers)
    assert status == 204
