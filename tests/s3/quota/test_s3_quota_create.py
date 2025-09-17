from tests.factory.s3_quota import S3QuotaCreatePayloadFactory


def test_s3_quota_create(headers_factory, api, aqa_acc, s3_ssd, clean_up_s3_quota):
    header = headers_factory.build()
    payload = S3QuotaCreatePayloadFactory.build(pool_id=s3_ssd.id, account_name=aqa_acc.name)
    code, quota = api.s3.quotas.create(payload, header)
    clean_up_s3_quota(quota["id"])
    assert code == 201, f"unexpected_code: {code}"
    assert quota["id"] is not None, f"Creating fail {quota}"
