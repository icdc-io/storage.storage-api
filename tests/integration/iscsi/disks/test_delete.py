import pytest

from tests.factories.headers import HeadersPayload
from tests.support.iscsi_ceph import verify_disk_absent


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_operator_can_delete_ceph_disk_in_each_pool(
    api,
    env,
    pool_name,
):
    """Operator can delete Ceph-backed disk in any pool."""
    disk_ctx = env.disk_scope(pool_name=pool_name)
    disk = disk_ctx.disk
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.delete(disk.id, headers)

    assert status == 204
    assert verify_disk_absent(disk)
