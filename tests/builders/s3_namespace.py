from dataclasses import dataclass, field
from typing import Iterable

from app.models.s3_user import S3UserStatus
from tests.builders.account_namespace import AccountEnv, ScopeGuard, load_pools
from tests.factories.bucket import BucketFactory
from tests.factories.s3_quota import S3QuotaFactory
from tests.factories.s3_user import (
    ACTIVE_USER_QUOTA,
    EMPTY_USER_USAGE,
    S3UserFactory,
    build_user_state,
)

DEFAULT_POOL_NAME = "nvme"


@dataclass
class S3ScopeContext:
    account: object
    quota: object
    pool_name: str


@dataclass
class S3UserContext:
    account: object
    quota: object
    pool_name: str
    user: object


@dataclass
class BucketContext:
    account: object
    quota: object
    pool_name: str
    user: object
    bucket: object


@dataclass
class S3Env(AccountEnv, ScopeGuard):
    s3_pools: dict = field(default_factory=dict)
    ceph: object = None
    _scope_keys: set[tuple[int, int]] = field(
        default_factory=set,
        init=False,
    )

    def __post_init__(self):
        if not self.s3_pools:
            self.s3_pools = load_pools("s3")

    def quota(self, *, account, pool_name: str = DEFAULT_POOL_NAME, **kwargs):
        return S3QuotaFactory.create(
            account_id=account.id,
            pool_id=self.s3_pools[pool_name].id,
            **kwargs,
        )

    def quotas(self, *, account, pool_names: Iterable[str], **kwargs):
        return [
            self.quota(account=account, pool_name=pool_name, **kwargs)
            for pool_name in pool_names
        ]

    def user(
        self,
        *,
        account,
        pool_name: str = DEFAULT_POOL_NAME,
        **kwargs,
    ):
        pool = self.s3_pools[pool_name]
        quota = kwargs.pop("quota", None)
        usage = kwargs.pop("usage", None)
        status = kwargs.pop("status", S3UserStatus.ACTIVE)
        keys = kwargs.pop("keys", None)
        kwargs.setdefault("account_name", account.name)
        s3_user = S3UserFactory.create(
            account_id=account.id,
            pool_id=pool.id,
            **kwargs,
        )
        self.inject_user_state(
            s3_user,
            quota=quota,
            usage=usage,
            status=status,
            keys=keys,
        )
        return s3_user

    def inject_user_state(
        self,
        user,
        *,
        quota=None,
        usage=None,
        status=S3UserStatus.ACTIVE,
        keys=None,
    ):
        quota = quota or ACTIVE_USER_QUOTA.copy()
        usage = usage or EMPTY_USER_USAGE.copy()
        if self.ceph:
            return self.ceph.register_user_state(
                user,
                quota=quota,
                usage=usage,
                status=status,
                keys=keys,
            )

        state = build_user_state(
            user.name,
            quota=quota,
            usage=usage,
            status=status,
            keys=keys,
        )
        user.inject_ceph_state(state)
        return state

    def bucket(self, *, s3_user, **kwargs):
        bucket = BucketFactory.build(s3_user=s3_user, **kwargs)
        if self.ceph:
            return self.ceph.register_bucket(bucket)
        return bucket

    def scope(
        self,
        *,
        account=None,
        pool_name: str = DEFAULT_POOL_NAME,
        **quota_kwargs,
    ):
        account = account or self.account()
        pool = self.s3_pools[pool_name]
        self._register_scope(
            kind="S3",
            account=account,
            pool_name=pool_name,
            pool=pool,
            keys=self._scope_keys,
        )
        quota = self.quota(
            account=account,
            pool_name=pool_name,
            **quota_kwargs,
        )
        return S3ScopeContext(
            account=account,
            quota=quota,
            pool_name=pool_name,
        )

    def user_scope(
        self,
        *,
        account=None,
        pool_name: str = DEFAULT_POOL_NAME,
        **user_kwargs,
    ):
        scope = self.scope(
            account=account,
            pool_name=pool_name,
        )
        s3_user = self.user(
            account=scope.account,
            pool_name=pool_name,
            **user_kwargs,
        )
        return S3UserContext(
            account=scope.account,
            quota=scope.quota,
            pool_name=scope.pool_name,
            user=s3_user,
        )

    def bucket_scope(
        self,
        *,
        account=None,
        pool_name: str = DEFAULT_POOL_NAME,
        **bucket_kwargs,
    ):
        user_ctx = self.user_scope(
            account=account,
            pool_name=pool_name,
        )
        bucket = self.bucket(s3_user=user_ctx.user, **bucket_kwargs)
        return BucketContext(
            account=user_ctx.account,
            quota=user_ctx.quota,
            pool_name=user_ctx.pool_name,
            user=user_ctx.user,
            bucket=bucket,
        )
