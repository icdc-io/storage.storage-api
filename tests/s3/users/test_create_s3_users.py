import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import S3UserCreatePayloadFactory
from tests.schemes.s3_user import S3UserTestResponseSchema


def test_s3_user_create(aqa, s3_pool, clean_up_s3_user, api):
    header = HeadersPayload.build(operator=True)
    payload = S3UserCreatePayloadFactory.create(account_name=aqa.name, pool_id=s3_pool.id)
    code, user = api.s3.users.create(payload, header)
    clean_up_s3_user(user["name"])
    assert code == 201, f"{user}"
    try:
        S3UserTestResponseSchema().load(user)
    except ValidationError as e:
        pytest.fail(f"S3 User validation failed: {e.messages}")

