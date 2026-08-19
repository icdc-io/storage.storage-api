import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskUpdatePayload
from tests.support.iscsi_ceph import verify_disk_size_gb


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_disk_size_gb_update_ceph(api, env, pool_name):
    """Disk size change should be applied in Ceph."""
    disk_ctx = env.disk_scope(pool_name=pool_name)
    disk = disk_ctx.disk
    size_gb = disk.size_gb
    payload = IscsiDiskUpdatePayload.build(
        size_gb=size_gb + 1,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.update(disk.id, payload, headers)

    assert status == 200
    assert disk.size_gb == size_gb + 1
    assert verify_disk_size_gb(disk)
