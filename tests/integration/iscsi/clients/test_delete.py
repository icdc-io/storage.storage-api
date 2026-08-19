import pytest

from tests.factories.headers import HeadersPayload
from tests.support.iscsi_ceph import verify_client_exists


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_delete_client_requires_unassign_in_single_pool(
    api,
    assigned_ceph_factory,
    ceph_unassign_client,
    pool_name,
):
    """Client cannot be deleted while disks are assigned in a single pool."""
    headers = HeadersPayload.build(operator=True)
    client = assigned_ceph_factory(disk_pools=pool_name)

    status, body = api.iscsi.clients.delete(client.id, headers)
    assert status == 409
    assert verify_client_exists(client, pool_name)

    ceph_unassign_client(client)

    status, body = api.iscsi.clients.delete(client.id, headers)
    assert status == 204
