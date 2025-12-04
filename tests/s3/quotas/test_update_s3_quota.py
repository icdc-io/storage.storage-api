from tests.factories.headers import HeadersPayload
from tests.factories.s3_quota import S3QuotaPayloadFactory


def test_s3_quota_update(s3_quota, api):
    header = HeadersPayload.build(operator=True)
    payload = S3QuotaPayloadFactory.build(
        users=6,
        buckets=11,
        objects=21,
        data_size_mb=101
    )
    code, quota = api.s3.quotas.update(s3_quota.id, payload, header)
    assert code == 200, f"unexpected_code: {code}"
    assert quota["users"] == 6
    assert quota["buckets"] == 11
    assert quota["objects"] == 21
    assert quota["data_size_mb"] == 101
