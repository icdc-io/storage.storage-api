import pytest
from sqlalchemy import delete

from app.lib.ceph_utils import ceph_connection as rgwadmin_conn

from tests.factory.s3_user import S3UserCreatePayloadFactory


@pytest.fixture(scope="package")
def seed_s3_users(api, headers_factory_scope_package, aqa_acc, s3_ssd, clean_up_s3_user_pkg):
    payload = S3UserCreatePayloadFactory.build(name="buckets", pool_id=s3_ssd.id, account_id=aqa_acc.id)
    header = headers_factory_scope_package.build()
    users_list = []
    for n in range(7, 8):
        payload["name"] = f"user_{n}"
        code, user = api.s3.users.create(payload, header)
        assert code in (200, 201), f"{user}"
        users_list.append(user)
        clean_up_s3_user_pkg(user["name"])

    users = {user["name"]: user for user in users_list}
    yield users


@pytest.fixture
def clean_up_s3_user(ceph_cleanup_registry):
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
def s3_user(api, headers_factory, aqa_acc, s3_ssd, clean_up_s3_user):
    payload = S3UserCreatePayloadFactory.build(pool_id=s3_ssd.id, account_id=aqa_acc.id)
    header = headers_factory.build()

    code, user = api.s3.users.create(payload, header)
    assert code in (200, 201)
    clean_up_s3_user(user["name"])
    yield user


@pytest.fixture(scope="function")
def locked_s3_user(client, s3_user, headers_factory):
    headers = headers_factory()
    r = client.put(f"/api/v2/s3/users/{s3_user['id']}", json={"status": "lock"}, headers=headers)
    state = r.get_json()
    assert state["status"] == "locked"
    return s3_user
