import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_gateway import IscsiGatewayPayload


def test_operator_create_gateway_returns_204(api, cluster):
    """Operator can create a gateway (204 No Content)."""
    payload = IscsiGatewayPayload.build(cluster_id=cluster.id)
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.gateways.create(payload=payload, hdr=headers)

    assert status == 204
    assert body in (None, "", {})


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_cannot_create_gateway(api, account, cluster, role):
    """Only operator can create gateways."""
    payload = IscsiGatewayPayload.build(cluster_id=cluster.id)
    headers = HeadersPayload.build(account=account.name, role=role)
    status, body = api.iscsi.gateways.create(payload=payload, hdr=headers)

    assert status == 403
    assert "forbidden" in str(body).lower()


def test_create_gateway_missing_cluster_id_returns_404(api):
    """Missing cluster_id returns 404."""
    payload = IscsiGatewayPayload.build(cluster_id=None)
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.gateways.create(payload=payload, hdr=headers)

    assert status == 404
    assert "not found" in str(body).lower()


@pytest.mark.parametrize(
    "bad_name",
    [
        "", None, " ",
        "GW",
        "gateway with space",
        "gateway/illegal",
        "GATEWAY_CAPS",
        "gateway-@",
    ],
)
def test_create_gateway_invalid_name_returns_400(api, cluster, bad_name):
    """Invalid gateway name should return 400."""
    payload = IscsiGatewayPayload.build(cluster_id=cluster.id, name=bad_name)
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.gateways.create(payload=payload, hdr=headers)

    assert status == 400
    assert "name" in str(body).lower()
