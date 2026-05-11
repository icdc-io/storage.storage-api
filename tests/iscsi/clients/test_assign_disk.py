import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiAssignedClientPayload
from tests.fixtures.iscsi_client import verify_disk_assignment


def test_member_can_assign_own_client_and_disk(
    api,
    target,
    client,
    disk_db_factory,
):
    """Member can assign a disk they own to their own client."""
    account = client.account
    disk = disk_db_factory(target=target, owner=client.owner)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk in client.disks


def test_member_cannot_assign_non_own_client(
    api,
    client,
    disk_db,
):
    """Member cannot assign a disk to a client they do not own."""
    account = client.account

    payload = IscsiAssignedClientPayload.build(disk_db)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=disk_db.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Client not found."


def test_member_cannot_assign_non_own_disk(
    api,
    client,
    disk_db,
):
    """Member cannot assign a disk they do not own, even for their own client."""
    account = client.account

    payload = IscsiAssignedClientPayload.build(disk_db)
    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Disk not found."


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_and_owner_can_assign_account_client_and_disk(
    api,
    client,
    disk_db,
    role,
):
    """Admin and owner can assign disks to a client in their own account."""
    account = client.account

    payload = IscsiAssignedClientPayload.build(disk_db)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk_db in client.disks


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_assign_client_in_other_account(
    api,
    account_factory,
    client,
    disk_db,
    role,
):
    """Member/admin/owner cannot assign disk to a client in another account."""
    account = account_factory(count=1)

    payload = IscsiAssignedClientPayload.build(disk_db)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Client not found."


@pytest.mark.parametrize("role", ["member", "admin", "owner"])
def test_roles_cannot_assign_disk_in_other_account(
    api,
    account_factory,
    target,
    client,
    disk_db_factory,
    role,
):
    """Member/admin/owner cannot assign a disk that belongs to another account."""
    account = account_factory(count=1)
    disk = disk_db_factory(target=target, owner=client.owner)

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(
        account=account.name,
        role=role,
        user=client.owner,
    )

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404, "Client not found."


def test_operator_can_assign_client_in_any_account(
    api,
    client,
    disk_db,
):
    """Operator can assign disks to clients in any account."""
    payload = IscsiAssignedClientPayload.build(disk_db)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 201, "Disk assigned successfully."
    assert disk_db in client.disks


def test_operator_cannot_assign_client_and_disk_of_different_accounts(
    api,
    client,
    disk_db_factory,
):
    """Operator cannot assign disk and client from different accounts."""
    disk = disk_db_factory()

    payload = IscsiAssignedClientPayload.build(disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 400


def test_assign_disk_to_nonexistent_client_returns_404(
    api,
    disk_db,
):
    """Assigning disk to non-existent client should return 404."""
    payload = IscsiAssignedClientPayload.build(disks=disk_db)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=0,
        payload=payload,
        header=headers,
    )

    assert status == 404


def test_assign_nonexistent_disk_to_client_returns_404(
    api,
    client,
):
    """Assigning non-existent disk to client should return 404."""
    payload = IscsiAssignedClientPayload.build(disks=0)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status == 404


def test_assign_already_assigned_disk_succeeds(api, client_db_assigned):
    """Re-assigning an already assigned disk should succeed (idempotent)."""
    payload = IscsiAssignedClientPayload.build(
        disks=client_db_assigned.disks,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client_db_assigned.id,
        payload=payload,
        header=headers,
    )

    assert status == 201


@pytest.mark.ceph
def test_assign_single_disk_to_client_in_ceph(
    api,
    aqa_client,
    disk_ceph,
):
    """Assign a single disk to client and sync to Ceph."""
    payload = IscsiAssignedClientPayload.build(disks=disk_ceph)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=aqa_client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    assert disk_ceph in aqa_client.disks
    assert verify_disk_assignment(
        aqa_client,
        disk_ceph,
    ), "Disk assigned successfully in Ceph."


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_assign_disk_from_specific_pool(
    api,
    aqa_client,
    disk_ceph_factory,
    pool_name,
):
    """Assign a single disk from specific storage pool to client."""
    disk = disk_ceph_factory(disk_pools=pool_name)
    payload = IscsiAssignedClientPayload.build(disks=disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=aqa_client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    assert disk in aqa_client.disks
    assert verify_disk_assignment(
        aqa_client,
        disk,
    ), "Disk assigned successfully in Ceph."


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_assign_disks_from_specific_pool(
    api,
    aqa_client,
    disk_ceph_factory,
    pool_name,
):
    """Assign multiple disks from specific storage pool to client."""
    disks = disk_ceph_factory(disk_pools=pool_name, count=2)
    payload = IscsiAssignedClientPayload.build(disks=disks)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=aqa_client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    for disk in disks:
        assert disk in aqa_client.disks
    assert verify_disk_assignment(
        aqa_client,
        disks,
    ), "Disks assigned successfully in Ceph."


@pytest.mark.ceph
def test_assign_multiple_disks_across_all_pools(
    api,
    aqa_client,
    disk_ceph_factory,
    target_pools
):
    """Assign one disk from each available storage pool to a single client."""
    disks = disk_ceph_factory(disk_pools=target_pools)
    payload = IscsiAssignedClientPayload.build(disks=disks)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=aqa_client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    for disk in (disks if isinstance(disks, list) else [disks]):
        assert disk in aqa_client.disks
    assert verify_disk_assignment(
        aqa_client,
        disks,
    ), "Disks assigned successfully in Ceph."
