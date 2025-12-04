from tests.factories.bucket import BucketCreatePayloadFactory
from tests.factories.headers import HeadersPayload


def test_create_bucket(s3_user, api):
    header = HeadersPayload.build(operator=True)
    payload = BucketCreatePayloadFactory.build(user_name=s3_user["name"])
    code, bucket = api.s3.buckets.create(payload, header)
    assert code == 201, f"{bucket}"
