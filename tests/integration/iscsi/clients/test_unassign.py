import pytest

from tests.factories.headers import HeadersPayload
from tests.support.iscsi_ceph import (
    verify_client_exists,
    verify_disk_assignment,
)


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_unassign_disk_from_client_in_ceph(
    api,
    env,
    pool_name,
):
    """Unassign disk from client in Ceph and remove client when last disk gone."""
    client = env.client()
    scope_ctx = env.scope(pool_name=pool_name)
    disk = env.disk(target=scope_ctx.target)
    env.assign(client=client, disks=disk)

    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk.id,
        header=headers,
    )

    assert status == 204
    assert not verify_disk_assignment(client, disk)
    assert not verify_client_exists(client, pool_name)


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_unassign_multiple_disks_in_pool(
    api,
    env,
    pool_name,
):
    """Unassign multiple disks in one pool; client removed after last disk."""
    client = env.client()
    scope_ctx = env.scope(pool_name=pool_name)
    disk1, disk2 = env.disks(target=scope_ctx.target, count=2)
    env.assign(client=client, disks=[disk1, disk2])

    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk1.id,
        header=headers,
    )

    assert status == 204
    assert verify_disk_assignment(client, disk1) is False
    assert verify_client_exists(client, pool_name) is True

    status, body = api.iscsi.client_disks.unassign(
        client_id=client.id,
        disk_id=disk2.id,
        header=headers,
    )

    assert status == 204
    assert verify_disk_assignment(client, disk2) is False
    assert verify_client_exists(client, pool_name) is False
