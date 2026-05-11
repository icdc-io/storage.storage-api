import pytest

from tests.factories.headers import HeadersPayload


def test_operator_can_delete_any_quota(api, iscsi_quota):
    """Operator can delete any existing quota."""
    hdr = HeadersPayload.build(operator=True)
    st, _ = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st == 204

    st2, body2 = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st2 == 404
    assert "not found" in str(body2).lower()


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_delete_own_quota(api, iscsi_quota, role):
    """Owner/Admin can delete only their own iscsi quotas."""
    hdr = HeadersPayload.build(account=iscsi_quota.account.name, role=role)
    st, _ = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st == 204


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_delete_other_quota(api, account_factory, iscsi_quota, role):
    """Owner/Admin cannot delete iscsi quotas of another account."""
    account = account_factory(1)
    hdr = HeadersPayload.build(account=account.name, role=role)
    st, body = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st == 404
    assert "permission" in str(body).lower() or "not found" in str(body).lower()


def test_member_cannot_delete_quota(api, iscsi_quota):
    """Member cannot delete any iscsi quota."""
    hdr = HeadersPayload.build(account=iscsi_quota.account.name, role="member")
    st, body = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st == 403
    assert "forbidden" in str(body).lower()


def test_delete_nonexistent_quota_returns_404(api):
    """Deleting a non-existent iscsi quota should return 404."""
    hdr = HeadersPayload.build(operator=True)
    st, body = api.iscsi.quotas.delete(999999, hdr=hdr)
    assert st == 404
    assert "not found" in str(body).lower()


def test_delete_quota_with_existing_target_prohibit(api, iscsi_quota, target):
    """Delete iscsi quota with existing target is prohibited"""
    hdr = HeadersPayload.build(operator=True)
    st, body = api.iscsi.quotas.delete(iscsi_quota.id, hdr=hdr)
    assert st == 409
