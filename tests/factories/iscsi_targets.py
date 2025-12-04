from app.models.iscsi_target import IscsiTargets
from tests.factories.base import BaseFactory, DictFactory


class IscsiTargetFactory(BaseFactory):
    """Factory for creating real IscsiTargets in DB."""
    class Meta:
        model = IscsiTargets

    cluster_id: int
    pool_id: int


class IscsiTargetPayload(DictFactory):
    """Payload factories for API (no DB insert)."""
    cluster_id: int
    pool_id: int
