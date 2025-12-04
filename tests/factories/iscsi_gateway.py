import uuid
from typing import Iterable, List

import factory

from app.models.iscsi_gateway import IscsiGateways
from tests.factories.base import BaseFactory, DictFactory


def _gen_gw_name() -> factory.Sequence:
    """Generate unique gateway name."""
    return factory.Sequence(lambda n: f"cloudgw-testgw{n}")


def _gen_ip(prefix: str, n: int) -> str:
    """Generate sequential IP like <prefix>.X.Y."""
    third = n // 255
    fourth = (n % 255) + 1
    return f"{prefix.rstrip('.')}.{third}.{fourth}"


class IscsiGatewayFactory(BaseFactory):
    """Factory for creating real IscsiGateways in DB."""
    class Meta:
        model = IscsiGateways

    name = factory.Sequence(lambda n: f"cloudgw-testgw{n}")
    portal_ip_address = factory.Sequence(lambda n: _gen_ip(prefix="17.17", n=n))
    ip_address = factory.Sequence(lambda n: _gen_ip(prefix="21.21", n=n))
    cloudgw_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    api_user = "api_user"
    api_password = "api_password"
    cluster_id: int

    @classmethod
    def create_aqa_gateways(cls, *, gateways=None, **common) -> List[IscsiGateways]:
        """Create multiple AQA gateways for a cluster."""
        data: Iterable[dict] = gateways or cls.Params.aqa_gateways
        return [cls.create(**g, **common) for g in data]


class IscsiGatewayPayload(DictFactory):
    """Payload factories for API (no DB insert)."""
    name = factory.Sequence(lambda n: f"cloudgw-name{n}")
    portal_ip_address = factory.Sequence(lambda n: _gen_ip(prefix="99.99", n=n))
    ip_address = factory.Sequence(lambda n: _gen_ip(prefix="14.14", n=n))
    cloudgw_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    api_user = "api_user"
    api_password = "api_password"
    cluster_id: int
