import factory

from app.models.s3_user import S3Users, S3UserStatus
from tests.factories.base import BaseFactory, BasePayloadFactory

ACTIVE_USER_QUOTA = {"data_size_mb": 1, "objects": 1, "buckets": 1}
EMPTY_USER_USAGE = {"data_size_mb": 0, "objects": 0, "buckets": 0}
DELETED_USER_QUOTA = EMPTY_USER_USAGE
TYPICAL_USER_QUOTA = {"data_size_mb": 10, "objects": 10, "buckets": 10}
OVERSIZED_USER_QUOTA = {"data_size_mb": 10000, "buckets": 10000, "objects": 10000}


def build_user_keys(user_name):
    return {
        "s3": {
            "access_key": "fake_access_key",
            "secret_key": "fake_secret_key",
            "user": user_name,
        },
        "swift": {
            "secret_key": "fake_swift_secret_key",
            "user": f"{user_name}:swift",
        },
    }


def build_user_state(user_name, *, quota=None, usage=None, status=None, keys=None):
    return {
        "status": status or S3UserStatus.ACTIVE,
        "quota": quota or ACTIVE_USER_QUOTA.copy(),
        "usage": usage or EMPTY_USER_USAGE.copy(),
        "keys": keys or build_user_keys(user_name),
    }


class S3UserFactory(BaseFactory):
    class Meta:
        model = S3Users

    class Params:
        account_name = "test-account"

    description = factory.Sequence(lambda n: f"s3 user {n}")
    owner = factory.Sequence(lambda n: f"s3_owner{n}@example.com")
    name = factory.LazyAttributeSequence(
        lambda obj, n: f"{obj.account_name}$user_{n}"
    )
    account_id: int
    pool_id: int


class S3UserCreatePayloadFactory(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"testing_{n + 200}")
    owner = "owner@example.com"
    account_name = None
    account_id = None
    pool_id = None
    quota = factory.LazyFunction(lambda: ACTIVE_USER_QUOTA.copy())

    class Params:
        typical_quota = factory.Trait(
            quota=factory.LazyFunction(lambda: TYPICAL_USER_QUOTA.copy()),
        )


class S3UserUpdatePayloadFactory(BasePayloadFactory):
    owner = None
    status = None
    description = None
    quota = None
