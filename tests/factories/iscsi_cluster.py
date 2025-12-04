import factory

from app.models.iscsi_cluster import IscsiClusters
from tests.factories.base import BaseFactory, BasePayloadFactory


class IscsiClusterFactory(BaseFactory):
    class Meta:
        model = IscsiClusters

    name = factory.Sequence(lambda n: f"cluster-bbbb{n + 1000}")
    account_id: int  # must be passed explicitly


class IscsiClusterPayload(BasePayloadFactory):
    """API payload factories expecting account_name instead of account_id."""
    name = factory.Sequence(lambda n: f"cluster-aaaa{n + 1000}")
    account_name: str  # must be passed explicitly
