import factory

from app.models.iscsi_quota import IscsiQuotas
from tests.factories.base import BaseFactory, DictFactory


class IscsiQuotaFactory(BaseFactory):
    """Factory for creating real IscsiQuotas in DB."""
    class Meta:
        model = IscsiQuotas

    account_id: int
    pool_id: int
    data_size_gb: int
    snapshots: int
    clients: int
    disks: int

    class Params:
        # Default test values
        default = factory.Trait(
            data_size_gb=20,
            snapshots=6,
            clients=4,
            disks=10,
        )
        big = factory.Trait(
            data_size_gb=10000,
            snapshots=10000,
            clients=10000,
            disks=10000,
        )


def get_limitset(pool_id: int):
    """Return quota limits directly from model."""
    return IscsiQuotas.get_pool_limitset(pool_id)


class IscsiQuotaPayload(DictFactory):
    """Payload factories for API (no DB insert)."""
    account_name: int
    pool_id: int
    data_size_gb: int
    snapshots: int
    clients: int
    disks: int

    class Params:
        # Default payload values
        default = factory.Trait(
            data_size_gb=20,
            snapshots=6,
            clients=4,
            disks=10,
        )
        # Minimum values for validation tests
        min = factory.Trait(
            data_size_gb=1,
            snapshots=1,
            clients=1,
            disks=1,
        )
