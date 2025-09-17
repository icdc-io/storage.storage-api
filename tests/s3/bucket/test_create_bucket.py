from tests.factory.bucket import BucketCreatePayloadFactory
from tests.factory.headers import HeadersFactory


def test_create_bucket(s3_user, api):
    header = HeadersFactory.build()
    payload = BucketCreatePayloadFactory.build(user_name=s3_user["name"])
    code, bucket = api.s3.buckets.create(payload, header)
    assert code == 201, f"{bucket}"
