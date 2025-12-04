import factory

from app.models.iscsi_disk import IscsiDisks
from tests.factories.base import BaseFactory, DictFactory


class IscsiDiskFactory(BaseFactory):
    """Factory for iSCSI disks."""

    class Meta:
        model = IscsiDisks

    name = factory.Sequence(lambda n: f"test_disk{n}")
    owner = factory.Sequence(lambda n: f"disk_owner{n}@example.com")
    size_gb: int
    target_id: int


class IscsiDiskPayload(DictFactory):
    """
    Pure payload factories for API. By default, valid payload.
    target_id is not included — only account_name and pool_id are required.
    """

    name = factory.Sequence(lambda n: f"test_name{n}")
    owner = factory.Sequence(lambda n: f"owner_example{n}@example.com")
    size_gb: int
    account_name: str
    pool_id: int
