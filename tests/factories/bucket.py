import factory

from app.models.bucket import Bucket
from tests.factories.base import BasePayloadFactory

UNLIMITED_BUCKET_QUOTA = {
    "data_size_mb": -1,
    "objects": -1,
}
SMALL_BUCKET_QUOTA = {
    "data_size_mb": 1,
    "objects": 1,
}
TYPICAL_BUCKET_QUOTA = {
    "data_size_mb": 2,
    "objects": 2,
}
EMPTY_BUCKET_USAGE = {
    "data_size_mb": 0,
    "objects": 0,
    "multipart_objects": 0,
    "total_objects": 0,
}


def build_bucket_path(user_name, bucket_name):
    account_name = user_name.split("$")[0] if "$" in user_name else ""
    return f"{account_name}/{bucket_name}" if account_name else bucket_name


def build_bucket_quota(quota=None):
    quota = quota or UNLIMITED_BUCKET_QUOTA
    return {
        "data_size_mb": quota.get("data_size_mb", -1),
        "objects": quota.get("objects", -1),
    }


def build_bucket_usage(usage=None):
    return usage or EMPTY_BUCKET_USAGE.copy()


class BucketFactory(factory.Factory):
    class Meta:
        model = Bucket

    class Params:
        s3_user = None

    name = factory.Sequence(lambda n: f"bucket{n}")
    user_name = factory.LazyAttribute(
        lambda obj: obj.s3_user.name if obj.s3_user is not None else "test-account$user"
    )
    path = factory.LazyAttribute(lambda obj: build_bucket_path(obj.user_name, obj.name))
    quota = factory.LazyFunction(build_bucket_quota)
    usage = factory.LazyFunction(build_bucket_usage)


class BucketCreatePayloadFactory(BasePayloadFactory):
    name = factory.Sequence(lambda n: f"bucket{n}")
    quota = factory.LazyFunction(lambda: UNLIMITED_BUCKET_QUOTA.copy())

    class Params:
        small_quota = factory.Trait(
            quota=factory.LazyFunction(lambda: SMALL_BUCKET_QUOTA.copy()),
        )
        typical_quota = factory.Trait(
            quota=factory.LazyFunction(lambda: TYPICAL_BUCKET_QUOTA.copy()),
        )
        unlimited_quota = factory.Trait(
            quota=factory.LazyFunction(lambda: UNLIMITED_BUCKET_QUOTA.copy()),
        )
