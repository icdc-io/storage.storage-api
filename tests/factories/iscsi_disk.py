import factory

from app.models.iscsi_disk import IscsiDisks
from tests.factories.base import BaseFactory, BasePayloadFactory


class IscsiDiskFactory(BaseFactory):
    class Meta:
        model = IscsiDisks

    name = factory.Sequence(lambda n: f"test_disk{n}")
    owner = factory.Sequence(lambda n: f"disk_owner{n}@example.com")
    size_gb = 1
    target_id: int

    class Params:
        minimal_size = factory.Trait(size_gb=1)
        small_size = factory.Trait(size_gb=2)
        resize_size = factory.Trait(size_gb=3)


class IscsiDiskCreatePayload(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"test_name_aqa{n}")
    owner = factory.Sequence(lambda n: f"owner_disk{n}@example.com")
    size_gb = 1
    account_name: str
    pool_id: int

    class Params:
        minimal_size = factory.Trait(size_gb=1)


class IscsiDiskUpdatePayload(BasePayloadFactory):
    size_gb = 1

    class Params:
        changed_owner = factory.Trait(owner="new_disk_owner@example.com")
