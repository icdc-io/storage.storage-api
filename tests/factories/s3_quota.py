import factory

from app.models.s3_quota import S3Quotas
from tests.factories.base import BaseFactory, BasePayloadFactory


class S3QuotaFactory(BaseFactory):
    """Factory for creating real S3Quotas in DB."""
    class Meta:
        model = S3Quotas

    account_id: int
    pool_id: int
    users: int
    buckets: int
    objects: int
    data_size_mb: int

    class Params:
        # Default test values
        default = factory.Trait(
            users=5,
            buckets=10,
            objects=20,
            data_size_mb=100,
        )


class S3QuotaPayloadFactory(BasePayloadFactory):
    """Payload factories for API (no DB insert)."""
    users: int
    buckets: int
    objects: int
    data_size_mb: int

    class Params:
        # Default payload values
        default = factory.Trait(
            users=5,
            buckets=10,
            objects=20,
            data_size_mb=100,
        )
        # Minimum values for validation tests
        min = factory.Trait(
            users=1,
            buckets=1,
            objects=1,
            data_size_mb=1,
        )
