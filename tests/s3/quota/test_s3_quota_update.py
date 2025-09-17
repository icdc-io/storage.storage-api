from tests.factory.s3_quota import S3QuotaUpdatePayloadFactory


def test_s3_quota_update(s3_quota, headers_factory, api, aqa_acc, s3_ssd):
    header = headers_factory.build()
    payload = S3QuotaUpdatePayloadFactory.build(
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
