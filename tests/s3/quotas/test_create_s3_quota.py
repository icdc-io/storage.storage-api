import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.s3_quota import S3QuotaPayloadFactory


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_s3_quota_create(api, account, s3_pool, role):
    header = HeadersPayload.build(account=account.name, role=role)
    payload = S3QuotaPayloadFactory.build(default=True, pool_id=s3_pool.id, account_name=account.name)
    code, quota = api.s3.quotas.create(payload, header)
    assert code == 201, f"unexpected_code: {code}"
    assert quota.get("id", None) is not None, f"Creating fail {quota}"
