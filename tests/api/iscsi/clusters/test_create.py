import pytest
from marshmallow import ValidationError

from app.models.iscsi_cluster import IscsiClusters
from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_cluster import IscsiClusterPayload
from tests.schemes.iscsi_cluster import IscsiClusterResponseTestSchema


def test_operator_can_create_cluster_with_real_db_state(api, env):
    """Operator can create a cluster for any account."""
    account = env.account()
    payload = IscsiClusterPayload.build(account_name=account.name)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clusters.create(payload=payload, header=headers)

    assert status in (200, 201)
    try:
        IscsiClusterResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")

    cluster = IscsiClusters.query.filter_by(id=body["id"]).first()
    assert cluster is not None
    assert cluster.account_id == account.id
    assert cluster.name == payload["name"]


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_roles_cannot_create_cluster(api, env, role):
    """Non-operator roles must not be able to create clusters."""
    account = env.account()
    payload = IscsiClusterPayload.build(account_name=account.name)
    headers = HeadersPayload.build(account=account.name, role=role)
    status, body = api.iscsi.clusters.create(payload=payload, header=headers)

    assert status == 403
    assert "forbidden" in str(body).lower()


def test_create_cluster_missing_account_name_result_create_cluster_for_subject_account(api):
    """If no account name is given, cluster is created for operator account."""
    payload = IscsiClusterPayload.build()
    headers = HeadersPayload.build(operator=True)
    status, body = api.iscsi.clusters.create(payload=payload, header=headers)

    assert status == 201
    assert body["account"]["name"] == "devel"
    try:
        IscsiClusterResponseTestSchema().load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")
