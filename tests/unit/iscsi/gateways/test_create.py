import pytest
from marshmallow import ValidationError

from app.models.iscsi_gateway import IscsiGatewaySchema
from tests.factories.iscsi_gateway import IscsiGatewayPayload


def make_create_gateway_body(**overrides):
    cluster_id = overrides.pop("cluster_id", 1)
    body = IscsiGatewayPayload.build(cluster_id=cluster_id, **overrides)
    body["cluster_id"] = cluster_id
    return body


@pytest.mark.parametrize(
    "valid_name",
    [
        "gateway01",
        "gateway-01",
        "gateway.name_2",
        "a" * 64,
    ],
)
def test_gateway_schema_accepts_valid_name(valid_name):
    loaded = IscsiGatewaySchema().load(make_create_gateway_body(name=valid_name))

    assert loaded["name"] == valid_name


@pytest.mark.parametrize(
    "invalid_name",
    [
        "gateway name",
        "gateway@name",
        "A" * 65,
        "",
        None,
        "bad/name",
    ],
)
def test_gateway_schema_rejects_invalid_name(invalid_name):
    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(make_create_gateway_body(name=invalid_name))

    assert "name" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_ip",
    [
        "10.0.0.1",
        "192.168.1.10",
        "2001:db8::1",
    ],
)
def test_gateway_schema_accepts_valid_portal_ip_address(valid_ip):
    loaded = IscsiGatewaySchema().load(
        make_create_gateway_body(portal_ip_address=valid_ip)
    )

    assert loaded["portal_ip_address"] == valid_ip


@pytest.mark.parametrize(
    "invalid_ip",
    [
        "999.999.999.999",
        "bad-ip",
        "",
        None,
    ],
)
def test_gateway_schema_rejects_invalid_portal_ip_address(invalid_ip):
    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(
            make_create_gateway_body(portal_ip_address=invalid_ip)
        )

    assert "portal_ip_address" in exc_info.value.messages


@pytest.mark.parametrize(
    "valid_ip",
    [
        "10.0.1.1",
        "172.16.0.5",
        "2001:db8::2",
    ],
)
def test_gateway_schema_accepts_valid_ip_address(valid_ip):
    loaded = IscsiGatewaySchema().load(
        make_create_gateway_body(ip_address=valid_ip)
    )

    assert loaded["ip_address"] == valid_ip


@pytest.mark.parametrize(
    "invalid_ip",
    [
        "999.999.999.999",
        "bad-ip",
        "",
        None,
    ],
)
def test_gateway_schema_rejects_invalid_ip_address(invalid_ip):
    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(make_create_gateway_body(ip_address=invalid_ip))

    assert "ip_address" in exc_info.value.messages


@pytest.mark.parametrize("valid_cluster_id", [1, 2, 999])
def test_gateway_schema_accepts_valid_cluster_id(valid_cluster_id):
    loaded = IscsiGatewaySchema().load(
        make_create_gateway_body(cluster_id=valid_cluster_id)
    )

    assert loaded["cluster_id"] == valid_cluster_id


@pytest.mark.parametrize("invalid_cluster_id", ["bad", None])
def test_gateway_schema_rejects_invalid_cluster_id(invalid_cluster_id):
    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(
            make_create_gateway_body(cluster_id=invalid_cluster_id)
        )

    assert "cluster_id" in exc_info.value.messages


@pytest.mark.parametrize(
    "missing_field",
    [
        "name",
        "portal_ip_address",
        "ip_address",
        "cloudgw_id",
        "api_user",
        "api_password",
        "cluster_id",
    ],
)
def test_gateway_schema_rejects_missing_required_field(missing_field):
    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(
            make_create_gateway_body(**{missing_field: None})
        )

    assert missing_field in exc_info.value.messages


def test_gateway_schema_rejects_extra_field():
    payload = make_create_gateway_body()
    payload["extra_field"] = "error"

    with pytest.raises(ValidationError) as exc_info:
        IscsiGatewaySchema().load(payload)

    assert "extra_field" in exc_info.value.messages
