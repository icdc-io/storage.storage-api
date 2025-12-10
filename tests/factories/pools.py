from app.models.pool import Pools
from tests.factories.base import BaseFactory


class PoolFactory(BaseFactory):
    """Factory for creating real Pools in DB."""
    class Meta:
        model = Pools

    type: str
    name: str
    klass: str
