import pytest

from tests.builders.s3_namespace import BucketContext
from tests.factories.headers import HeadersPayload
from tests.schemes.bucket import BucketResponseTestSchema
from tests.support.assertions import assert_schema_response


def validate_response(body):
    assert_schema_response(
        body,
        BucketResponseTestSchema,
        many=True,
        message="Bucket response validation failed",
    )


def list_buckets(api, headers, query=None):
    status_code, response_body = api.s3.buckets.list(query=query, header=headers)

    assert status_code == 200
    validate_response(response_body)
    return response_body


def assert_bucket_paths(response_body, buckets):
    assert {item["path"] for item in response_body} == {
        bucket.path for bucket in buckets
    }


def add_bucket(
    env,
    *,
    name,
    user_name=None,
    scope=None,
    **scope_kwargs,
):
    if user_name is not None:
        scope_kwargs["name"] = user_name
    if scope is None:
        user_ctx = env.user_scope(**scope_kwargs)
        bucket = env.bucket(s3_user=user_ctx.user, name=name)
        return BucketContext(
            account=user_ctx.account,
            quota=user_ctx.quota,
            pool_name=user_ctx.pool_name,
            user=user_ctx.user,
            bucket=bucket,
        )

    user = env.user(
        account=scope.account,
        pool_name=scope.pool_name,
        **scope_kwargs,
    )
    bucket = env.bucket(s3_user=user, name=name)
    return BucketContext(
        account=scope.account,
        quota=scope.quota,
        pool_name=scope.pool_name,
        user=user,
        bucket=bucket,
    )


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_list_only_own_account_buckets(
    api,
    env,
    role,
):
    """Owner and admin should only see buckets from their own account."""
    own_account, foreign_account = env.accounts(count=2)
    own_bucket_one = add_bucket(
        env,
        account=own_account,
        name="own-account-bucket-one",
        user_name=f"{own_account.name}$own-account-user-one",
    ).bucket
    own_bucket_two = add_bucket(
        env,
        account=own_account,
        pool_name="ssd",
        name="own-account-bucket-two",
        user_name=f"{own_account.name}$own-account-user-two",
    ).bucket
    add_bucket(
        env,
        account=foreign_account,
        name="foreign-account-bucket",
        user_name=f"{foreign_account.name}$foreign-account-user",
    )

    headers = HeadersPayload.build(account=own_account.name, role=role)
    response_body = list_buckets(api, headers)

    assert_bucket_paths(response_body, [own_bucket_one, own_bucket_two])


def test_member_lists_only_own_buckets(api, env):
    """Member should only see buckets for S3 users owned by the authenticated user."""
    account, foreign_account = env.accounts(count=2)
    member_owner = "member-bucket-owner@example.com"
    nvme_scope = env.scope(account=account, pool_name="nvme")
    ssd_scope = env.scope(account=account, pool_name="ssd")
    foreign_scope = env.scope(account=foreign_account)
    own_bucket_one = add_bucket(
        env,
        scope=nvme_scope,
        owner=member_owner,
        name="member-own-bucket-one",
        user_name=f"{account.name}$member-own-user-one",
    ).bucket
    own_bucket_two = add_bucket(
        env,
        scope=ssd_scope,
        owner=member_owner,
        name="member-own-bucket-two",
        user_name=f"{account.name}$member-own-user-two",
    ).bucket
    add_bucket(
        env,
        scope=nvme_scope,
        owner="same-account-other@example.com",
        name="member-hidden-same-account",
        user_name=f"{account.name}$member-hidden-same-account",
    )
    add_bucket(
        env,
        scope=foreign_scope,
        owner=member_owner,
        name="member-hidden-foreign-account",
        user_name=f"{foreign_account.name}$member-hidden-foreign-account",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_buckets(api, headers)

    assert_bucket_paths(response_body, [own_bucket_one, own_bucket_two])


@pytest.mark.parametrize("role", ["owner", "admin", "member"])
def test_non_operator_account_filter_does_not_override_scope(
    api,
    env,
    role,
):
    """Foreign account_id filters should not widen non-operator scope."""
    own_account, foreign_account = env.accounts(count=2)
    own_bucket_ctx = add_bucket(
        env,
        account=own_account,
        name="scope-own-bucket",
        user_name=f"{own_account.name}$scope-own-user",
    )
    own_bucket = own_bucket_ctx.bucket
    add_bucket(
        env,
        account=foreign_account,
        name="scope-foreign-bucket",
        user_name=f"{foreign_account.name}$scope-foreign-user",
    )

    headers_kwargs = {"account": own_account.name, "role": role}
    if role == "member":
        headers_kwargs["user"] = own_bucket_ctx.user.owner
    headers = HeadersPayload.build(**headers_kwargs)

    response_body = list_buckets(
        api,
        headers,
        query={"account_id": foreign_account.id},
    )

    assert_bucket_paths(response_body, [own_bucket])


def test_member_owner_filter_does_not_override_scope(
    api,
    env,
):
    """Owner filters should not let a member reach another user's buckets."""
    account = env.account()
    member_owner = "member-bucket-filter@example.com"
    scope = env.scope(account=account)
    own_bucket = add_bucket(
        env,
        scope=scope,
        owner=member_owner,
        name="member-filter-own-bucket",
        user_name=f"{account.name}$member-filter-own-user",
    ).bucket
    foreign_owner_ctx = add_bucket(
        env,
        scope=scope,
        owner="other-bucket-owner@example.com",
        name="member-filter-hidden-bucket",
        user_name=f"{account.name}$member-filter-hidden-user",
    )

    headers = HeadersPayload.build(
        account=account.name,
        role="member",
        user=member_owner,
    )
    response_body = list_buckets(
        api,
        headers,
        query={"owner": foreign_owner_ctx.user.owner},
    )

    assert_bucket_paths(response_body, [own_bucket])


def test_operator_filters_buckets_by_name(api, env):
    """Operator should be able to filter buckets by bucket name."""
    account = env.account()
    scope = env.scope(account=account)
    matching_bucket = add_bucket(
        env,
        scope=scope,
        name="operator-name-match",
        user_name=f"{account.name}$operator-name-user-one",
    ).bucket
    add_bucket(
        env,
        scope=scope,
        name="operator-name-hidden",
        user_name=f"{account.name}$operator-name-user-two",
    )

    headers = HeadersPayload.build(operator=True)
    response_body = list_buckets(
        api,
        headers,
        query={"name": matching_bucket.name},
    )

    assert_bucket_paths(response_body, [matching_bucket])


def test_operator_filters_buckets_by_owner(api, env):
    """Operator should be able to filter buckets through parent S3 user owner."""
    account = env.account()
    matching_owner = "operator-bucket-owner@example.com"
    scope = env.scope(account=account)
    matching_bucket = add_bucket(
        env,
        scope=scope,
        owner=matching_owner,
        name="operator-owner-match",
        user_name=f"{account.name}$operator-owner-match-user",
    ).bucket
    add_bucket(
        env,
        scope=scope,
        owner="operator-bucket-other@example.com",
        name="operator-owner-hidden",
        user_name=f"{account.name}$operator-owner-hidden-user",
    )

    headers = HeadersPayload.build(operator=True)
    response_body = list_buckets(
        api,
        headers,
        query={"owner": matching_owner},
    )

    assert_bucket_paths(response_body, [matching_bucket])


def test_operator_combines_bucket_and_user_filters(
    api,
    env,
):
    """Operator should get the exact intersection of bucket and parent filters."""
    account = env.account()
    matching_owner = "bucket-combo-owner@example.com"
    scope = env.scope(account=account)
    matching_bucket = add_bucket(
        env,
        scope=scope,
        owner=matching_owner,
        name="bucket-combo-match",
        user_name=f"{account.name}$bucket-combo-match-user",
    ).bucket
    add_bucket(
        env,
        scope=scope,
        owner="bucket-combo-other@example.com",
        name="bucket-combo-match",
        user_name=f"{account.name}$bucket-combo-other-user",
    )
    add_bucket(
        env,
        scope=scope,
        owner=matching_owner,
        name="bucket-combo-hidden",
        user_name=f"{account.name}$bucket-combo-hidden-user",
    )

    headers = HeadersPayload.build(operator=True)
    response_body = list_buckets(
        api,
        headers,
        query={
            "name": matching_bucket.name,
            "owner": matching_owner,
        },
    )

    assert_bucket_paths(response_body, [matching_bucket])


def test_list_bucket_response_shape(api, env):
    """Bucket list should serialize path, owner user, quota, and usage."""
    bucket_ctx = add_bucket(
        env,
        name="shape-bucket",
    )

    headers = HeadersPayload.build(
        account=bucket_ctx.account.name,
        role="member",
        user=bucket_ctx.user.owner,
    )
    response_body = list_buckets(
        api,
        headers,
        query={"name": bucket_ctx.bucket.name},
    )

    assert len(response_body) == 1
    assert response_body[0]["path"] == bucket_ctx.bucket.path
    assert response_body[0]["user_name"] == bucket_ctx.user.name
    assert response_body[0]["quota"] == bucket_ctx.bucket.quota
    assert response_body[0]["usage"] == bucket_ctx.bucket.usage
