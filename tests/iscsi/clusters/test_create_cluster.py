import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_cluster import IscsiClusterPayload
from tests.schemes.iscsi_cluster import IscsiClusterResponseTestSchema


@pytest.mark.parametrize(
    "good_name",
    [
        "cluster-00000000",
        "cluster-ffffffff",
        "cluster-deabbeef",
        "cluster-1234abcd",
        "cluster-abcdef12",
        "cluster-00ff00ff",
        "cluster-a1b2c3d4",
        "cluster-01020304",
        "cluster-c0ffee00",
        "cluster-bad1cafe",
        "cluster-5e1fd0c0",
        "cluster-0a1b2c3d",
    ],
)
def test_operator_create_cluster_valid_name_returns_201(api, account, good_name):
    """Operator can create cluster with valid name."""
    payload = IscsiClusterPayload.build(account_name=account.name, name=good_name)
    header = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.create(payload=payload, header=header)

    assert status in (200, 201)
    try:
        IscsiClusterResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_cannot_create_cluster(api, account, role):
    """Non-operator roles must not be able to create clusters."""
    payload = IscsiClusterPayload.build(account_name=account.name)
    headers = HeadersPayload.build(account=account.name, role=role)
    status, body = api.iscsi.clusters.create(payload=payload, hdr=headers)

    assert status == 403
    assert "forbidden" in str(body).lower()


@pytest.mark.parametrize(
    "bad_name",
    [
        "cluster-test1234",
        "cluster-XYZ12345",
        "cluster-1234567",
        "cluster-123456789",
        "cluster_abcdef12",
        "cluster-abc1234g",
        "cluster-",
        "cluster",
        "",
        None,
    ],
)
def test_create_cluster_invalid_name_returns_400(api, account, bad_name):
    """Invalid cluster name should return 400."""
    payload = IscsiClusterPayload.build(account_name=account.name, name=bad_name)
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.create(payload=payload, hdr=headers)

    assert status == 400
    assert "name" in str(body).lower()


def test_create_cluster_missing_account_name_result_create_cluster_for_subject_account(api):
    """If no account name is given, cluster is created for operator account."""
    payload = IscsiClusterPayload.build()
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.create(payload=payload, hdr=headers)

    assert status == 201
    assert body["account"]["name"] == "devel"
    try:
        IscsiClusterResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")
