import pytest

from app.lib.s3.service import CephService
from app.models.s3_user import S3Users
from tests.factories.headers import HeadersPayload


def assert_user_removed_from_ceph_and_db(s3_user):
    assert S3Users.query.filter_by(id=s3_user.id).first() is None
    assert CephService().admin.get_user_info(s3_user.name) == {}


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_delete_user_removes_user_from_ceph(api, env, pool_name):
    user_ctx = env.user_scope(pool_name=pool_name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 204
    assert_user_removed_from_ceph_and_db(user_ctx.user)


def test_delete_already_deleted_user_returns_404(api, env):
    user_ctx = env.user_scope()
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.delete(user_ctx.user.id, headers)
    assert status == 204

    status, body = api.s3.users.delete(user_ctx.user.id, headers)

    assert status == 404
    assert (
        body["message"]
        == "This account hasn't got the user with this ID or you haven't access for it."
    )
    assert_user_removed_from_ceph_and_db(user_ctx.user)


def test_delete_user_with_buckets_removes_user_without_error(api, env):
    bucket_ctx = env.bucket_scope()
    second_bucket = env.bucket(s3_user=bucket_ctx.user)
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.users.delete(bucket_ctx.user.id, headers)

    assert second_bucket.user_name == bucket_ctx.user.name
    assert status == 204
    assert_user_removed_from_ceph_and_db(bucket_ctx.user)
