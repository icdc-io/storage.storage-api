from uuid import uuid4

import pytest

from app.models.iscsi_disk import IscsiDisks
from app.models.snapshot import Snapshots
from tests.factories.headers import HeadersPayload


def test_member_can_delete_own_disk(api, env):
    """Member can delete their own iSCSI disk."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    headers = HeadersPayload.build(
        account=disk_ctx.account.name,
        role="member",
        user=disk_ctx.disk.owner,
    )

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 204
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is None


def test_member_cannot_delete_non_own_disk(api, env):
    """Member cannot delete a disk they do not own."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    headers = HeadersPayload.build(
        account=disk_ctx.account.name,
        role="member",
        user="other_user@example.com",
    )

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 404, "Disk not found."
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is not None


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_or_owner_can_delete_disk_in_own_account(api, env, role):
    """Admin and owner can delete disks in their own account."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    headers = HeadersPayload.build(account=disk_ctx.account.name, role=role)

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 204
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is None


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_delete_disk_in_other_account(api, env, role):
    """Non-operator roles cannot delete a disk in another account."""
    owner_disk_ctx = env.disk_scope(pool_name="nvme")
    foreign_account = env.account()
    headers = HeadersPayload.build(
        account=foreign_account.name,
        role=role,
        user=owner_disk_ctx.disk.owner,
    )

    status, body = api.iscsi.disks.delete(owner_disk_ctx.disk.id, headers)

    assert status == 404, "Disk not found."
    assert IscsiDisks.query.filter_by(id=owner_disk_ctx.disk.id).first() is not None


def test_operator_can_delete_disk_in_any_account(api, env):
    """Operator can delete a disk in any account."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 204
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is None


def test_delete_nonexistent_disk_returns_404(api):
    """Deleting a nonexistent disk returns 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(99999, headers)

    assert status == 404, "Disk not found."


def test_cannot_delete_assigned_disk(api, env):
    """Deleting an assigned disk returns 409."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    client = env.client(account=disk_ctx.account)
    env.assign(client=client, disks=disk_ctx.disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 409
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is not None


def test_cannot_delete_disk_with_snapshots(api, env):
    """Deleting a disk with snapshots returns 409 and keeps the disk."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    snapshot = Snapshots(
        name=f"delete-blocking-snapshot-{uuid4().hex[:8]}",
        size_gb=disk_ctx.disk.size_gb,
        provisioned=disk_ctx.disk.size_gb,
        disk_id=disk_ctx.disk.id,
    )
    snapshot.save()
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 409
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is not None


def test_can_delete_disk_after_unassign(api, env):
    """Deleting a disk succeeds after it has been unassigned from its client."""
    disk_ctx = env.disk_scope(pool_name="nvme")
    client = env.client(account=disk_ctx.account)
    env.assign(client=client, disks=disk_ctx.disk)
    headers = HeadersPayload.build(operator=True)

    client.disks.remove(disk_ctx.disk)
    client.save()

    status, body = api.iscsi.disks.delete(disk_ctx.disk.id, headers)

    assert status == 204
    assert IscsiDisks.query.filter_by(id=disk_ctx.disk.id).first() is None
