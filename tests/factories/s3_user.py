import factory

from tests.factories.base import BasePayloadFactory


class S3UserCreatePayloadFactory(BasePayloadFactory):
    """Payload factories for creating S3 users (no DB insert)."""
    name = factory.Sequence(lambda n: f"testing_{n + 200}")
    owner = "owner@example.com"
    account_name = None
    pool_id = None
    quota = {"data_size_mb": 1, "buckets": 1, "objects": 1}

    class Params:
        # Common quota variants for testing
        good_quota = {"data_size_mb": 4, "buckets": 4, "objects": 4}
        bad_quota = {"data_size_mb": 10000}


class S3UserUpdatePayloadFactory(BasePayloadFactory):
    """Payload factories for updating S3 users."""
    owner = None
    status = None
    description = None
    quota = None

    class Params:
        # Reusable traits for specific scenarios
        lock = factory.Trait(status="lock")
        unlock = factory.Trait(status="unlock")
        good = factory.Trait(quota={"data_size_mb": 3, "buckets": 3, "objects": 3})
        use_default = factory.Trait(
            owner="new_owner@example.com",
            description="new description",
            quota={"data_size_mb": 3, "buckets": 3, "objects": 3},
        )
