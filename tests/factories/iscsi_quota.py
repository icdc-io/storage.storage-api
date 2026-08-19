import factory

from app.models.iscsi_quota import IscsiQuotas
from tests.factories.base import BaseFactory, BasePayloadFactory


class IscsiQuotaFactory(BaseFactory):
    """Factory for creating real IscsiQuotas in DB."""
    class Meta:
        model = IscsiQuotas

    account_id: int
    pool_id: int
    data_size_gb = 10_000
    snapshots = 10_000
    clients = 10_000
    disks = 10_000

    class Params:
        typical_limits = factory.Trait(
            data_size_gb=10,
            snapshots=10,
            clients=10,
            disks=10,
        )
        constrained_limits = factory.Trait(
            data_size_gb=20,
            snapshots=6,
            clients=4,
            disks=10,
        )
        minimal_limits = factory.Trait(
            data_size_gb=1,
            snapshots=1,
            clients=1,
            disks=1,
        )


def get_limitset(pool_id: int):
    """Return quota limits directly from model."""
    return IscsiQuotas.get_pool_limitset(pool_id)


class IscsiQuotaPayload(BasePayloadFactory):
    account_name = None
    pool_id = None
    target = None
    data_size_gb = 10
    snapshots = 10
    clients = 10
    disks = 10

    class Params:
        typical_limits = factory.Trait(
            data_size_gb=10,
            snapshots=10,
            clients=10,
            disks=10,
        )
        constrained_limits = factory.Trait(
            data_size_gb=20,
            snapshots=6,
            clients=4,
            disks=10,
        )
        minimal_limits = factory.Trait(
            data_size_gb=1,
            snapshots=1,
            clients=1,
            disks=1,
        )


class IscsiQuotaUpdatePayload(BasePayloadFactory):
    data_size_gb = None
    snapshots = None
    clients = None
    disks = None
