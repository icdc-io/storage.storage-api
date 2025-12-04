import pytest

from tests.factories.headers import HeadersPayload


def test_operator_can_delete_any_s3_quota(api, s3_quota):
    """Operator can delete any existing s3 quota."""
    hdr = HeadersPayload.build(operator=True)
    st, _ = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st == 204

    st2, body2 = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st2 == 404
    assert "not found" in str(body2).lower()


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_delete_own_s3_quota(api, s3_quota, role):
    """Owner/Admin can delete only their own s3 quotas."""
    hdr = HeadersPayload.build(account=s3_quota.account.name, role=role)
    st, _ = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st == 204


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_delete_other_s3_quota(api, account_factory, s3_quota, role):
    """Owner/Admin cannot delete s3 quotas of another account."""
    account = account_factory(1)
    hdr = HeadersPayload.build(account=account.name, role=role)
    st, body = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st == 404
    assert "permission" in str(body).lower() or "not found" in str(body).lower()


def test_member_cannot_delete_s3_quota(api, s3_quota):
    """Member cannot delete any s3 quota."""
    hdr = HeadersPayload.build(account=s3_quota.account.name, role="member")
    st, body = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st == 403
    assert "forbidden" in str(body).lower()


def test_delete_nonexistent_s3_quota_returns_404(api):
    """Deleting a non-existent s3 quota should return 404."""
    hdr = HeadersPayload.build(operator=True)
    st, body = api.s3.quotas.delete(999999, hdr=hdr)
    assert st == 404
    assert "not found" in str(body).lower()


# TODO: Correct it when wrtie code related to fake s3_user
def test_delete_s3_quota_with_existing_user_prohibited(api, aqa, s3_user):
    """Delete quota with existing s3 User is prohibited"""
    hdr = HeadersPayload.build(operator=True)
    for s3_quota in aqa.s3_quotas:
        if s3_quota.pool_id == s3_user["pool"]["id"]:
            st, body = api.s3.quotas.delete(s3_quota.id, hdr=hdr)
    assert st == 409
