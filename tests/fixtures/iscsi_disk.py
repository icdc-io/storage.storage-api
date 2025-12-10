import pytest

from app.lib.request_utils import is_failed
from app.models.iscsi_disk import IscsiDisks
from tests.factories.iscsi_disk import (
    IscsiDiskCephFactory,
    IscsiDiskFactory,
)
from tests.fixtures.iscsi_target import aqa_targets


@pytest.fixture
def disk_db(target, iscsi_quota):
    """Create a single iSCSI disk in database only (no Ceph sync)."""
    return IscsiDiskFactory.create(target_id=target.id, default=True)


@pytest.fixture
def disk_db_factory(target_factory):
    """Smart factory to create iSCSI disks with automatic dependency creation.

    Automatically creates missing dependencies (cluster, target, quota)
    if not provided. Uses recursive pattern: disk → target → cluster → account.

    Args:
        target: Existing target to use (auto-creates if not provided).
        disk_pools: Pool name or list of pool names (default: "nvme").
        count: Number of disks to create per pool (default: 1).
        create_quota: Whether to auto-create quota (default: False).
        **kwargs: Additional parameters (size_gb, name, owner, etc.).

    Returns:
        Single disk if total created is 1, otherwise list of disks.
    """

    def _normalize_pools(pools):
        if pools is None:
            return ["nvme"]
        return [pools] if isinstance(pools, str) else pools

    def _create_disks(
        target=None,
        disk_pools="nvme",
        count=1,
        create_quota=False,
        **kwargs,
    ):
        pool_names = _normalize_pools(disk_pools)
        all_disks = []

        for pool_name in pool_names:
            if not target:
                pool_target = target_factory(
                    target_pools=pool_name,
                    create_quota=create_quota,
                )
            else:
                pool_target = target

            pool_disks = [
                IscsiDiskFactory.create(
                    target_id=pool_target.id,
                    default=True,
                    **kwargs,
                )
                for _ in range(count)
            ]

            all_disks.extend(pool_disks)

        return all_disks[0] if len(all_disks) == 1 else all_disks

    return _create_disks


@pytest.fixture
def disk_ceph(aqa, disk_cleaner):
    """Create a single iSCSI disk synchronized to Ceph."""
    targets = aqa_targets(aqa)
    disk = IscsiDiskCephFactory.create(target=targets["nvme"])
    disk_cleaner(disk)
    yield disk


@pytest.fixture
def disk_ceph_factory(aqa, disk_cleaner):
    """Factory to create iSCSI disks synchronized to Ceph.

    Creates real disks in both Ceph storage and database.
    Automatically schedules cleanup after test completion.

    Args:
        disk_pools: Pool name or list of pool names (default: "nvme").
        count: Number of disks to create per pool (default: 1).
        **kwargs: Additional parameters (size_gb, name, owner, etc.).

    Returns:
        Single disk if total created is 1, otherwise list of disks.
    """

    def _normalize_pools(pools):
        if pools is None:
            return ["nvme"]
        return [pools] if isinstance(pools, str) else pools

    def _create_ceph_disks(disk_pools="nvme", count=1, **kwargs):
        pool_names = _normalize_pools(disk_pools)
        targets = aqa_targets(aqa)
        all_disks = []

        for pool_name in pool_names:
            pool_disks = [
                IscsiDiskCephFactory.create(
                    target=targets[pool_name],
                    **kwargs,
                )
                for _ in range(count)
            ]
            all_disks.extend(pool_disks)

        disk_cleaner(all_disks)

        return all_disks[0] if len(all_disks) == 1 else all_disks

    yield _create_ceph_disks


@pytest.fixture
def disk_cleaner(cleaner):
    """Fixture to delete disks from database and optionally from Ceph."""

    def _delete_disks(disks=None, disk_ids=None, immediate=False):
        cleaner.delete(
            IscsiDisks,
            objects=disks,
            ids=disk_ids,
            immediate=immediate,
        )

    return _delete_disks


def verify_disk_size_gb(disk):
    iscsi_service = disk.target.iscsi_service()
    response = iscsi_service.update_disk(disk.name, {"size_gb": disk.size_gb})
    return is_failed(response)


def verify_disk_exists(disk):
    iscsi_service = disk.target.iscsi_service()
    response = iscsi_service.get_disk(disk.name)
    return not is_failed(response)
