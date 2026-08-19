import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_client import IscsiClientPayload
from tests.support.iscsi_ceph import verify_client_credentials


@pytest.mark.ceph
def test_update_credentials_across_all_pools(
    api,
    env,
):
    """Update CHAP credentials for a client with disks across all pools."""
    client = env.client()
    disks = [
        env.disk(target=scope_ctx.target)
        for scope_ctx in env.scopes()
    ]
    env.assign(client=client, disks=disks)

    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]
    assert verify_client_credentials(client)


@pytest.mark.ceph
def test_update_credentials_in_multiple_pools(
    api,
    env,
):
    """Update CHAP credentials for a client with nvme + ssd pools."""
    client = env.client()
    disks = [
        env.disk(target=scope_ctx.target)
        for scope_ctx in env.scopes(pool_names=["nvme", "ssd"])
    ]
    env.assign(client=client, disks=disks)

    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(client.id, payload, headers)

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]
    assert verify_client_credentials(client)


@pytest.mark.ceph
def test_update_credentials_for_unassigned_then_reassigned_client(
    api,
    env,
    ceph_unassign_client,
):
    """Update credentials when unassigned, then reassign disk and verify."""
    client = env.client()
    scope_ctx = env.scope(pool_name="nvme")
    disk = env.disk(target=scope_ctx.target)
    env.assign(client=client, disks=disk)

    ceph_unassign_client(client, client.disks)

    payload = IscsiClientPayload.build(updated_credentials=True)
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.clients.update(
        client.id,
        payload,
        headers,
    )

    assert status == 200
    assert body["chap_username"] == payload["chap_username"]
    assert body["chap_password"] == payload["chap_password"]

    env.assign(client=client, disks=[disk])

    assert verify_client_credentials(client)
