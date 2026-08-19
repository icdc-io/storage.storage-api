import pytest

from app.lib.s3.exceptions import CephServiceException
from app.lib.s3.service import CephService
from tests.factories.headers import HeadersPayload


def assert_bucket_removed_from_ceph(bucket):
    with pytest.raises(CephServiceException):
        CephService().get_bucket_by_path(bucket.path)


@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_delete_bucket_removes_bucket_from_ceph(api, env, pool_name):
    bucket_ctx = env.bucket_scope(pool_name=pool_name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.delete(bucket_ctx.bucket.path, headers)

    assert status == 204
    assert_bucket_removed_from_ceph(bucket_ctx.bucket)


def test_delete_missing_bucket_returns_404(api):
    headers = HeadersPayload.build(operator=True)

    status, body = api.s3.buckets.delete("missing-account/missing-bucket", headers)

    assert status == 404
    assert body["message"] == "Bucket with this name not found."
