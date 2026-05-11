import pytest
from sqlalchemy import delete

from app.lib.s3.client import ceph_connection as rgwadmin_conn
from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import S3UserCreatePayloadFactory


@pytest.fixture(scope="package")
def seed_s3_users(api, aqa, s3_pool, clean_up_s3_user_pkg):
    """Seed several test S3 users for AQA account."""
    payload = S3UserCreatePayloadFactory.build(
        name="buckets", pool_id=s3_pool.id, account_id=aqa.id
    )
    header = HeadersPayload.build(operator=True)
    users_list = []

    for n in range(7, 8):
        payload["name"] = f"user_{n}"
        code, user = api.s3.users.create(payload, header)
        assert code in (200, 201), f"{user}"
        users_list.append(user)
        clean_up_s3_user_pkg(user["name"])

    yield {u["name"]: u for u in users_list}


@pytest.fixture
def clean_up_s3_user(ceph_cleanup_registry):
    """Register cleanup for S3 user in Ceph and DB."""
    from app.database import db
    from app.models.s3_user import S3Users

    def register(name: str, purge_data: bool = True, delete_db: bool = True):
        ceph_cleanup_registry.append(
            lambda n=name, pd=purge_data: rgwadmin_conn().remove_user(n, purge_data=pd)
        )
        if delete_db:
            ceph_cleanup_registry.append(
                lambda n=name: (
                    db.session.execute(delete(S3Users).where(S3Users.name == n)),
                    db.session.flush(),
                )
            )
    return register


@pytest.fixture(scope="package")
def clean_up_s3_user_pkg(ceph_cleanup_registry_scope_package):
    """Same as above but package-scoped."""
    from app.database import db
    from app.models.s3_user import S3Users

    def register(name: str, purge_data: bool = True, delete_db: bool = True):
        ceph_cleanup_registry_scope_package.append(
            lambda n=name, pd=purge_data: rgwadmin_conn().remove_user(n, purge_data=pd)
        )
        if delete_db:
            ceph_cleanup_registry_scope_package.append(
                lambda n=name: (
                    db.session.execute(delete(S3Users).where(S3Users.name == n)),
                    db.session.flush(),
                )
            )
    return register


@pytest.fixture(scope="function")
def s3_user(api, aqa, s3_pool, clean_up_s3_user):
    """Create one temporary S3 user and register cleanup."""
    payload = S3UserCreatePayloadFactory.build(pool_id=s3_pool.id, account_id=aqa.id)
    header = HeadersPayload.build(account=aqa.name, role="owner")
    code, user = api.s3.users.create(payload, header)
    assert code in (200, 201)
    clean_up_s3_user(user["name"])
    yield user


@pytest.fixture(scope="function")
def locked_s3_user(flask_client, s3_user):
    """Lock existing S3 user via API and return it."""
    header = HeadersPayload.build(operator=True)
    r = flask_client.put(
        f"/api/v2/s3/users/{s3_user['id']}",
        json={"status": "locked"},
        headers=header,
    )
    state = r.get_json()
    assert state["status"] == "locked"
    return s3_user
