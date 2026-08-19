import pytest

from app.lib.s3.exceptions import CephServiceException
from app.lib.s3.service import CephService
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import TYPICAL_USER_QUOTA
from tests.schemes.bucket import BucketResponseTestSchema
from tests.support.assertions import assert_schema_response


def list_buckets(api, headers, query=None):
    status, body = api.s3.buckets.list(query=query, header=headers)

    assert status == 200
    assert_schema_response(
        body,
        BucketResponseTestSchema,
        many=True,
        message="Bucket response validation failed",
    )
    return body


def assert_bucket_paths(response_body, buckets):
    assert {bucket["path"] for bucket in response_body} == {
        bucket.path for bucket in buckets
    }


def test_list_buckets_reads_real_ceph_bucket_state(api, env):
    bucket_ctx = env.bucket_scope()
    headers = HeadersPayload.build(operator=True)

    response_body = list_buckets(
        api,
        headers,
        query={"name": bucket_ctx.bucket.name},
    )

    assert len(response_body) == 1
    assert response_body[0]["path"] == bucket_ctx.bucket.path
    assert response_body[0]["user_name"] == bucket_ctx.user.name
    assert response_body[0]["quota"] == bucket_ctx.bucket.quota


def test_list_buckets_returns_all_buckets_for_one_user_and_excludes_other_user(
    api,
    env,
):
    owner = "bucket-list-member@example.com"
    user_ctx = env.user_scope(owner=owner, user_quota=TYPICAL_USER_QUOTA.copy())
    own_bucket_one = env.bucket(s3_user=user_ctx.user)
    own_bucket_two = env.bucket(s3_user=user_ctx.user)
    other_user_ctx = env.user_scope(owner="other-bucket-list-member@example.com")
    env.bucket(s3_user=other_user_ctx.user)
    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user=owner,
    )

    response_body = list_buckets(api, headers)

    assert_bucket_paths(response_body, [own_bucket_one, own_bucket_two])


def test_get_bucket_by_path_reads_real_ceph_bucket_state(env):
    bucket_ctx = env.bucket_scope()

    bucket = CephService().get_bucket_by_path(bucket_ctx.bucket.path)

    assert bucket.path == bucket_ctx.bucket.path
    assert bucket.name == bucket_ctx.bucket.name
    assert bucket.user_name == bucket_ctx.user.name
    assert bucket.quota == bucket_ctx.bucket.quota


def test_get_bucket_by_path_missing_bucket_fails():
    with pytest.raises(CephServiceException):
        CephService().get_bucket_by_path("missing-account/missing-bucket")
