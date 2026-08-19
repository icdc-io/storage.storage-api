import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_gateway import IscsiGatewayPayload
from tests.support.assertions import assert_no_content_response


def test_operator_can_create_gateway(api, env):
    """Operator can create a gateway in any cluster."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = IscsiGatewayPayload.build(cluster_id=cluster.id)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.gateways.create(payload=payload, header=headers)

    assert_no_content_response(status, body)


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_role_cannot_create_gateway(api, env, role):
    """Owner, admin, and member cannot create gateways."""
    account = env.account()
    cluster = env.cluster(account=account)
    payload = IscsiGatewayPayload.build(cluster_id=cluster.id)
    headers = HeadersPayload.build(account=account.name, role=role)

    status, body = api.iscsi.gateways.create(payload=payload, header=headers)

    assert status == 403
    assert "forbidden" in str(body).lower()


def test_operator_cannot_create_gateway_without_cluster_id(api):
    """Gateway creation requires an existing cluster id."""
    payload = IscsiGatewayPayload.build(cluster_id=None)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.gateways.create(payload=payload, header=headers)

    assert status == 404
    assert "not found" in str(body).lower()
