import pytest

from tests.factories.headers import HeadersPayload
from tests.fixtures.iscsi_client import (
    verify_client_exists,
    verify_disk_assignment,
)


def test_member_can_unassign_own_client_and_disk(
    api,
    target,
    assigned_db_factory,
    client,
    disk_db_factory,
):
    """Member can unassign disk from their own client."""
    disk = disk_db_factory(target=target, owner=client.owner)
    assigned_client = assigned_db_factory(clients=client, disks=disk)

    headers = HeadersPayload.build(
        account=client.account.name,
        role="member",
        user=client.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=assigned_client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


def test_member_cannot_unassign_non_own_client(
    api,
    client_db_assigned,
):
    """Member cannot unassign disk from client they do not own."""
    disk = client_db_assigned.disks[0]

    headers = HeadersPayload.build(
        account=client_db_assigned.account.name,
        role="member",
        user=client_db_assigned.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client_db_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


def test_member_cannot_unassign_non_own_disk(
    api,
    client_db_assigned,
):
    """Member cannot unassign disk they do not own."""
    disk = client_db_assigned.disks[0]

    headers = HeadersPayload.build(
        account=client_db_assigned.account.name,
        role="member",
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client_db_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_or_owner_can_unassign_disk_in_own_account(
    api,
    client_db_assigned,
    role,
):
    """Admin/Owner can unassign disk in their own account."""
    disk = client_db_assigned.disks[0]

    headers = HeadersPayload.build(
        account=client_db_assigned.account.name,
        role=role,
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client_db_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_or_owner_cannot_unassign_disk_in_other_account(
    api,
    client_db_assigned,
    account_factory,
    role,
):
    """Admin/Owner cannot unassign disk in another account."""
    account = account_factory()
    disk = client_db_assigned.disks[0]

    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=disk.owner,
    )
    status, body = api.iscsi.client_disks.unassign(
        client_id=client_db_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 404


def test_operator_can_unassign_disk_in_any_account(
    api,
    client_db_assigned,
):
    """Operator can unassign disk in any account."""
    disk = client_db_assigned.disks[0]

    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.client_disks.unassign(
        client_id=client_db_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204


def test_unassign_disk_from_nonexistent_client_returns_404(
    api,
    disk_db,
):
    """Unassigning disk from non-existent client should return 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=0,
        disk_id=disk_db.id,
        header=headers,
    )

    assert status == 404


def test_unassign_nonexistent_disk_from_client_returns_404(
    api,
    client,
):
    """Unassigning non-existent disk from client should return 404."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=0,
        header=headers,
    )

    assert status == 404


def test_unassign_already_unassigned_disk_succeeds(
    api,
    client,
    disk_db,
):
    """Unassigning already unassigned disk should succeed (idempotent)."""
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk_db.id,
        header=headers,
    )

    assert status == 204


@pytest.mark.ceph
def test_unassign_disk_from_client_in_ceph(
    api,
    client_ceph_assigned,
):
    """Unassign disk from client in Ceph and remove client when last disk gone."""
    headers = HeadersPayload.build(operator=True)
    disk = client_ceph_assigned.disks[0]

    status, body = api.iscsi.client_disks.unassign(
        client_id=client_ceph_assigned.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204
    assert not verify_disk_assignment(client_ceph_assigned, disk)
    assert not verify_client_exists(client_ceph_assigned)


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_unassign_multiple_disks_in_pool(
    api,
    aqa_client,
    disk_ceph_factory,
    assigned_ceph_factory,
    pool_name,
):
    """Unassign multiple disks in one pool; client removed after last disk."""
    headers = HeadersPayload.build(operator=True)
    disk1, disk2 = disk_ceph_factory(disk_pools=pool_name, count=2)

    assigned_ceph_factory(clients=aqa_client, disks=[disk1, disk2])

    status, body = api.iscsi.client_disks.unassign(
        client_id=aqa_client.id,
        disk_id=disk1.id,
        header=headers,
    )

    assert status == 204
    assert verify_disk_assignment(aqa_client, disk1) is False
    assert verify_client_exists(aqa_client, pool_name) is True

    status, body = api.iscsi.client_disks.unassign(
        client_id=aqa_client.id,
        disk_id=disk2.id,
        header=headers,
    )

    assert status == 204
    assert verify_disk_assignment(aqa_client, disk2) is False
    assert verify_client_exists(aqa_client, pool_name) is False
