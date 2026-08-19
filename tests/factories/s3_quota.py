import factory

from app.models.s3_quota import S3Quotas
from tests.factories.base import BaseFactory, BasePayloadFactory


class S3QuotaFactory(BaseFactory):
    """Factory for creating real S3Quotas in DB."""
    class Meta:
        model = S3Quotas

    account_id: int
    pool_id: int
    users = 10_000
    buckets = 10_000
    objects = 10_000
    data_size_mb = 10_000

    class Params:
        typical_limits = factory.Trait(
            users=10,
            buckets=10,
            objects=10,
            data_size_mb=10,
        )
        constrained_limits = factory.Trait(
            users=5,
            buckets=10,
            objects=20,
            data_size_mb=100,
        )
        minimal_limits = factory.Trait(
            users=1,
            buckets=1,
            objects=1,
            data_size_mb=1,
        )


class S3QuotaPayloadFactory(BasePayloadFactory):
    account_name = None
    pool_id = None
    users = 10
    buckets = 10
    objects = 10
    data_size_mb = 10

    class Params:
        typical_limits = factory.Trait(
            users=10,
            buckets=10,
            objects=10,
            data_size_mb=10,
        )
        constrained_limits = factory.Trait(
            users=5,
            buckets=10,
            objects=20,
            data_size_mb=100,
        )
        minimal_limits = factory.Trait(
            users=1,
            buckets=1,
            objects=1,
            data_size_mb=1,
        )


class S3QuotaUpdatePayloadFactory(BasePayloadFactory):
    users = None
    buckets = None
    objects = None
    data_size_mb = None

    class Params:
        constrained_limits = factory.Trait(
            users=5,
            buckets=10,
            objects=20,
            data_size_mb=100,
        )
        increased_limits = factory.Trait(
            users=6,
            buckets=11,
            objects=21,
            data_size_mb=101,
        )
        minimal_limits = factory.Trait(
            users=1,
            buckets=1,
            objects=1,
            data_size_mb=1,
        )
