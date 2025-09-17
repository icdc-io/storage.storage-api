import factory

from tests.factory.base import BasePayloadFactory


class BucketCreatePayloadFactory(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"bucket")
    quota = {"data_size_mb": 1, "buckets": 1, "objects": 1}

    class Params:
        good_quota = {"data_size_mb": 4, "buckets": 4, "objects": 4}
        bad_quota = {"data_size_mb": 10000}
