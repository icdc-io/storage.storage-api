import factory

from app.lib.request_utils import is_failed
from app.models.iscsi_disk import IscsiDisks
from tests.factories.base import BaseFactory, DictFactory


class IscsiDiskFactory(BaseFactory):
    """Factory for creating iSCSI disk database models.

    Generates realistic test data for iSCSI disk objects with unique
    sequential values for names and owner emails.
    """

    class Meta:
        model = IscsiDisks

    name = factory.Sequence(lambda n: f"test_disk{n}")
    owner = factory.Sequence(lambda n: f"disk_owner{n}@example.com")
    size_gb: int
    target_id: int

    class Params:
        default = factory.Trait(size_gb=2)


class IscsiDiskCephFactory(IscsiDiskFactory):
    """Factory for creating iSCSI disks synchronized to Ceph.

    Creates both database record and actual disk in Ceph storage.
    Inherits from IscsiDiskFactory and extends functionality to
    interact with real Ceph cluster via iSCSI service.
    """

    @classmethod
    def create(cls, target, **kwargs):
        """Create iSCSI disk in both database and Ceph storage.

        Args:
            target: IscsiTarget object associated with this disk
            **kwargs: Additional parameters for disk creation (e.g., size_gb, name)

        Returns:
            IscsiDisk object with corresponding Ceph disk created
        """
        # Get iSCSI service interface for target
        iscsi_service = target.iscsi_service()

        # Ensure target_id is set from target object
        kwargs["target_id"] = target.id

        # Create database record with default trait applied
        disk = super().create(default=True, **kwargs)

        # Prepare Ceph API payload
        ceph_payload = {
            "name": disk.name,
            "size_gb": disk.size_gb
        }
        iscsi_service.delete_disk(disk.name)
        # Create actual disk in Ceph storage
        response = iscsi_service.create_disk(ceph_payload)
        if is_failed(response):
            raise ValueError(
                f"Failed to create disk '{disk.name}' in Ceph storage. "
                f"Response: {response}"
            )

        return disk


class IscsiDiskPayload(DictFactory):
    """Factory for creating iSCSI disk API payloads.

    Generates request payloads for disk creation via API.
    Uses account_name and pool_id instead of target_id for API compatibility.
    All payloads are valid by default.
    """

    name = factory.Sequence(lambda n: f"test_name{n}")
    owner = factory.Sequence(lambda n: f"owner_disk{n}@example.com")
    size_gb: int
    account_name: str
    pool_id: int

    class Params:
        manual = factory.Trait(name=None, owner=None)
        min = factory.Trait(size_gb=1)
        new_owner = factory.Trait(owner="new_disk_owner@example.com")
