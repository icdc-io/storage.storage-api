import pytest
from marshmallow import ValidationError

from tests.factory.s3_user import S3UserCreatePayloadFactory
from tests.schemes.s3_user import S3UserResponseSchema


def test_s3_user_create(accounts, s3_pools, headers_factory, clean_up_s3_user, api):
    header = headers_factory.build()
    payload = S3UserCreatePayloadFactory.create(account_name=accounts["aqa"].name, pool_id=s3_pools["ssd"].id)
    code, user = api.s3.users.create(payload, header)
    assert code == 201, f"{user}"
    clean_up_s3_user(user["name"])


def test_s3_user_create_fail(accounts, s3_pools, headers_factory, clean_up_s3_user, api):
    header = headers_factory.build()
    payload = S3UserCreatePayloadFactory.create(account_name=accounts["aqa"].name, pool_id=s3_pools["ssd"].id)
    code, user = api.s3.users.create(payload, header)
    assert code == 201, f"{user}"
    clean_up_s3_user(user["name"])
    try:
        S3UserResponseSchema().load(user)
    except ValidationError as e:
        pytest.fail(f"S3 User validation failed: {e.messages}")
