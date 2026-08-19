import pytest

from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import ACTIVE_USER_QUOTA, EMPTY_USER_USAGE
from tests.schemes.s3_user import S3UserTestResponseSchema
from tests.support.assertions import assert_schema_response


def validate_response(body, schema=S3UserTestResponseSchema, many=True):
    assert_schema_response(body, schema, many=many, message="S3 User validation failed")


def list_s3_users(api, headers, query=None):
    status_code, response_body = api.s3.users.list(query=query, header=headers)

    assert status_code == 200
    validate_response(response_body)
    return response_body


def assert_user_ids(response_body, users):
    assert {item["id"] for item in response_body} == {user.id for user in users}


def create_user_in(scope, env, **kwargs):
    return env.user(
        account=scope.account,
        pool_name=scope.pool_name,
        **kwargs,
    )


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_list_only_own_account_s3_users(api, env, role):
    """Owner and admin should only see S3 users from their own account."""
    own_account, foreign_account = env.accounts(count=2)
    own_nvme_scope = env.scope(account=own_account, pool_name="nvme")
    own_ssd_scope = env.scope(account=own_account, pool_name="ssd")
    foreign_scope = env.scope(account=foreign_account)
    own_user_one = create_user_in(own_nvme_scope, env)
    own_user_two = create_user_in(own_ssd_scope, env)
    create_user_in(foreign_scope, env)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_s3_users(api, headers)

    assert_user_ids(response_body, [own_user_one, own_user_two])


def test_member_lists_only_own_s3_users(api, env):
    """Member should only see S3 users owned by the authenticated user."""
    account, foreign_account = env.accounts(count=2)
    member_owner = "member-s3-owner@example.com"
    nvme_scope = env.scope(account=account, pool_name="nvme")
    ssd_scope = env.scope(account=account, pool_name="ssd")
    foreign_scope = env.scope(account=foreign_account)
    own_user_one = create_user_in(nvme_scope, env, owner=member_owner)
    own_user_two = create_user_in(
        ssd_scope,
        env,
        owner=member_owner,
    )
    create_user_in(nvme_scope, env, owner="same-account-other@example.com")
    create_user_in(foreign_scope, env, owner=member_owner)

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_s3_users(api, headers)

    assert_user_ids(response_body, [own_user_one, own_user_two])


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_ignores_foreign_account_filter(api, env, role):
    """Account-scoped roles should not widen scope with foreign account filters."""
    own_account, foreign_account = env.accounts(count=2)
    own_scope = env.scope(account=own_account)
    foreign_scope = env.scope(account=foreign_account)
    own_user = create_user_in(own_scope, env)
    create_user_in(foreign_scope, env)

    headers_kwargs = {"account": own_account.name, "role": role}
    if role == "member":
        headers_kwargs["user"] = own_user.owner
    headers = HeadersPayload.build(**headers_kwargs)

    response_body = list_s3_users(
        api,
        headers,
        query={"account_id": foreign_account.id},
    )

    assert_user_ids(response_body, [own_user])


def test_member_owner_filter_does_not_override_subject_scope(api, env):
    """Member owner filter should not override authenticated owner scope."""
    account = env.account()
    member_owner = "member-s3-filter@example.com"
    scope = env.scope(account=account)
    own_user = create_user_in(scope, env, owner=member_owner)
    foreign_owner_user = create_user_in(
        scope,
        env,
        owner="other-s3-owner@example.com",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_s3_users(
        api,
        headers,
        query={"owner": foreign_owner_user.owner},
    )

    assert_user_ids(response_body, [own_user])


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_account_filter_does_not_override_scope(api, env, role):
    """Owner/admin should not reach a foreign account through account_id filter."""
    own_account, foreign_account = env.accounts(count=2)
    own_scope = env.scope(account=own_account)
    foreign_scope = env.scope(account=foreign_account)
    own_user = create_user_in(own_scope, env)
    create_user_in(foreign_scope, env)

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_s3_users(
        api,
        headers,
        query={"account_id": foreign_account.id, "id": own_user.id},
    )

    assert_user_ids(response_body, [own_user])


def test_operator_filters_s3_users_by_name(api, env):
    """Operator should be able to filter S3 users by name."""
    account = env.account()
    scope = env.scope(account=account)
    matching_user = create_user_in(scope, env, name=f"{account.name}$name-match")
    create_user_in(scope, env, name=f"{account.name}$name-hidden")

    headers = HeadersPayload.build(operator=True)
    response_body = list_s3_users(
        api,
        headers,
        query={"name": matching_user.name},
    )

    assert_user_ids(response_body, [matching_user])


def test_operator_filters_s3_users_by_owner(api, env):
    """Operator should be able to filter S3 users by owner."""
    account = env.account()
    matching_owner = "s3-owner-filter@example.com"
    scope = env.scope(account=account)
    matching_user = create_user_in(scope, env, owner=matching_owner)
    create_user_in(scope, env, owner="other-s3-owner-filter@example.com")

    headers = HeadersPayload.build(operator=True)
    response_body = list_s3_users(
        api,
        headers,
        query={"owner": matching_owner},
    )

    assert_user_ids(response_body, [matching_user])


def test_operator_filters_s3_users_by_pool_class(api, env):
    """Operator should be able to filter S3 users by parent pool class."""
    account = env.account()
    ssd_scope = env.scope(account=account, pool_name="ssd")
    nvme_scope = env.scope(account=account, pool_name="nvme")
    matching_user = create_user_in(ssd_scope, env)
    create_user_in(nvme_scope, env)

    headers = HeadersPayload.build(operator=True)
    response_body = list_s3_users(
        api,
        headers,
        query={"account_id": account.id, "pool.class": "ssd"},
    )

    assert_user_ids(response_body, [matching_user])


def test_operator_combines_base_and_parent_filters(api, env):
    """Operator should get the exact intersection of base and parent filters."""
    account = env.account()
    matching_owner = "s3-combo-owner@example.com"
    ssd_scope = env.scope(account=account, pool_name="ssd")
    nvme_scope = env.scope(account=account, pool_name="nvme")
    matching_user = create_user_in(
        ssd_scope,
        env,
        owner=matching_owner,
    )
    create_user_in(ssd_scope, env, owner="s3-combo-other@example.com")
    create_user_in(nvme_scope, env, owner=matching_owner)

    headers = HeadersPayload.build(operator=True)
    response_body = list_s3_users(
        api,
        headers,
        query={
            "account_id": account.id,
            "owner": matching_owner,
            "pool.class": "ssd",
        },
    )

    assert_user_ids(response_body, [matching_user])


def test_list_s3_user_includes_mocked_ceph_state_in_response_body(api, env):
    """S3 user list should serialize mocked Ceph quota, usage, keys, and status."""
    user_ctx = env.user_scope(pool_name="nvme")

    headers = HeadersPayload.build(
        account=user_ctx.account.name,
        role="member",
        user=user_ctx.user.owner,
    )
    response_body = list_s3_users(
        api,
        headers,
        query={"id": user_ctx.user.id},
    )

    assert len(response_body) == 1
    assert response_body[0]["id"] == user_ctx.user.id
    assert response_body[0]["status"] == "active"
    assert response_body[0]["quota"] == ACTIVE_USER_QUOTA
    assert response_body[0]["usage"] == EMPTY_USER_USAGE
    assert response_body[0]["keys"]["s3"]["user"] == user_ctx.user.name
