from __future__ import annotations

from app.database import db
from app.lib.request_utils import is_failed
from tests.factories.iscsi_disk import IscsiDiskFactory


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value]


class IscsiOperations:
    """Imperative DB/Ceph-side test operations for mutable iSCSI resources."""

    @staticmethod
    def _is_retryable_4xx(response: dict) -> bool:
        code = response.get("code", 0)
        return 400 <= code < 500

    @classmethod
    def _retry_after_cleanup(cls, action, cleanup_if_exists):
        response = action()
        if cls._is_retryable_4xx(response):
            cleanup_if_exists()
            response = action()
        return response

    @staticmethod
    def create_ceph_disk(*, target, **kwargs):
        iscsi_service = target.iscsi_service()
        kwargs["target_id"] = target.id

        disk = IscsiDiskFactory.create(**kwargs)
        ceph_payload = {
            "name": disk.name,
            "size_gb": disk.size_gb,
        }

        response = IscsiOperations._retry_after_cleanup(
            lambda: iscsi_service.create_disk(ceph_payload),
            lambda: (
                iscsi_service.delete_disk(disk.name)
                if not is_failed(iscsi_service.get_disk(disk.name))
                else None
            ),
        )
        if is_failed(response):
            raise ValueError(
                f"Failed to create disk '{disk.name}' in Ceph storage. "
                f"Response: {response}"
            )

        return disk

    @classmethod
    def create_ceph_disks(cls, *, target, count: int, **kwargs):
        return [
            cls.create_ceph_disk(target=target, **kwargs)
            for _ in range(count)
        ]

    @staticmethod
    def assign_db(*, client, disks):
        for disk in _as_list(disks):
            client.disks.append(disk)
        db.session.commit()
        return client

    @classmethod
    def assign_ceph(cls, *, client, disks):
        assigned_disks = []
        for disk in _as_list(disks):
            iscsi_service = disk.target.iscsi_service()
            response = iscsi_service.assign_disk(client, disk.name)
            if cls._is_retryable_4xx(response):
                if not is_failed(iscsi_service.get_client(client.iqn)):
                    iscsi_service.delete_client(client.iqn)
                    response = {}
                    for retry_disk in [*assigned_disks, disk]:
                        response = iscsi_service.assign_disk(client, retry_disk.name)
                        if is_failed(response):
                            break
            if is_failed(response):
                raise ValueError(
                    f"Failed to assign disk '{disk.name}' to client '{client.iqn}' in Ceph. "
                    f"Response: {response}"
                )
            client.disks.append(disk)
            assigned_disks.append(disk)
        db.session.commit()
        return client
