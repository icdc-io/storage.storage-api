import pytest
from marshmallow import ValidationError

from app.models.iscsi_disk import IscsiDisks
from tests.factories.headers import HeadersPayload
from tests.factories.iscsi_disk import IscsiDiskCreatePayload
from tests.schemes import IscsiDiskResponseTestSchema
from tests.support.iscsi_ceph import verify_disk_exists


def validate_schema(body):
    try:
        IscsiDiskResponseTestSchema().load(body)
    except ValidationError as exc:
        pytest.fail(f"Response schema validation failed: {exc.messages}")


@pytest.mark.ceph
@pytest.mark.parametrize("pool_name", ["nvme", "ssd", "hdd"])
def test_operator_can_create_disk_in_any_pool(
    api,
    env,
    pool_name,
):
    """Operator can create a real Ceph-backed disk in any seeded pool."""
    scope_ctx = env.scopes_by_pool[pool_name]

    payload = IscsiDiskCreatePayload.build(
        pool_id=scope_ctx.quota.pool_id,
        account_name=env.account.name,
        size_gb=5,
    )
    headers = HeadersPayload.build(operator=True)

    status_code, response_body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status_code in (200, 201)
    validate_schema(response_body)

    created_disk = IscsiDisks.query.filter_by(id=response_body["id"]).first()
    assert created_disk is not None
    env.track_disk(created_disk)

    assert created_disk.target_id == scope_ctx.target.id
    assert created_disk.owner == payload["owner"]
    assert created_disk.size_gb == payload["size_gb"]
    assert created_disk.name == payload["name"]
    assert verify_disk_exists(created_disk), f"Disk was not created in Ceph for pool {pool_name}."
