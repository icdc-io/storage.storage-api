import factory
from tests.factory.base import BaseFactory, BasePayloadFactory
from app.models.s3_quota import S3Quotas


class S3QuotaFactory(BaseFactory):
    class Meta:
        model = S3Quotas

    account_id = None
    pool_id = None
    users = 5
    buckets = 10
    objects = 20
    data_size_mb = 100


class S3QuotaCreatePayloadFactory(BasePayloadFactory):
    users = 5
    buckets = 10
    objects = 20
    data_size_mb = 100

    class Params:
        users_overflow = 100000000


class S3QuotaUpdatePayloadFactory(BasePayloadFactory):
    users = 5
    buckets = 10
    objects = 20
    data_size_mb = 100

    class Params:
        users_overflow = 100000000
