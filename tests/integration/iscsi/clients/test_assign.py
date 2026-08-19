import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiAssignedClientPayload
from tests.support.iscsi_ceph import verify_disk_assignment


@pytest.mark.ceph
def test_assign_single_disk_to_client_in_ceph(
    api,
    env,
):
    """Assign a single disk to client and sync to Ceph."""
    client = env.client()
    scope_ctx = env.scope(pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)

    payload = IscsiAssignedClientPayload.build(disks=disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    assert disk in client.disks
    assert verify_disk_assignment(
        client,
        disk,
    ), "Disk assigned successfully in Ceph."


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_assign_disk_from_specific_pool(
    api,
    env,
    pool_name,
):
    """Assign a single disk from specific storage pool to client."""
    client = env.client()
    scope_ctx = env.scope(pool_name=pool_name)
    disk = env.disk(target=scope_ctx.target)

    payload = IscsiAssignedClientPayload.build(disks=disk)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    assert disk in client.disks
    assert verify_disk_assignment(
        client,
        disk,
    ), "Disk assigned successfully in Ceph."


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_assign_disks_from_specific_pool(
    api,
    env,
    pool_name,
):
    """Assign multiple disks from specific storage pool to client."""
    client = env.client()
    scope_ctx = env.scope(pool_name=pool_name)
    disks = env.disks(target=scope_ctx.target, count=2)

    payload = IscsiAssignedClientPayload.build(disks=disks)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    for disk in disks:
        assert disk in client.disks
    assert verify_disk_assignment(
        client,
        disks,
    ), "Disks assigned successfully in Ceph."


@pytest.mark.ceph
def test_assign_multiple_disks_across_all_pools(
    api,
    env,
):
    """Assign one disk from each available storage pool to a single client."""
    client = env.client()
    disks = [
        env.disk(target=scope_ctx.target)
        for scope_ctx in env.scopes()
    ]

    payload = IscsiAssignedClientPayload.build(disks=disks)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.assign(
        client_id=client.id,
        payload=payload,
        header=headers,
    )

    assert status in (200, 201)
    for disk in disks:
        assert disk in client.disks
    assert verify_disk_assignment(
        client,
        disks,
    ), "Disks assigned successfully in Ceph."
