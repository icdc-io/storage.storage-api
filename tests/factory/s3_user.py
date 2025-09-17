import factory

from tests.factory.base import BasePayloadFactory


class S3UserCreatePayloadFactory(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"testing_{n + 200}")
    owner = "owner@example.com"
    account_name = None
    pool_id = None
    quota = {"data_size_mb": 1, "buckets": 1, "objects": 1}

    class Params:
        good_quota = {"data_size_mb": 4, "buckets": 4, "objects": 4}
        bad_quota = {"data_size_mb": 10000}


class S3UserUpdatePayloadFactory(BasePayloadFactory):
    owner = None
    status = None
    description = None
    quota = None

    class Params:
        lock = factory.Trait(status="lock")
        unlock = factory.Trait(status="unlock")
        good = factory.Trait(quota={"data_size_mb": 3, "buckets": 3, "objects": 3})
        use_default = factory.Trait(owner="new_owner@example.com", description="new description", quota={"data_size_mb": 3, "buckets": 3, "objects": 3})
