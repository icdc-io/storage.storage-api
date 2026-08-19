from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from tests.builders.iscsi_namespace import (
    ClientContext,
    DiskContext,
    IscsiScopeContext,
)
from tests.builders.iscsi_operations import IscsiOperations
from tests.builders.s3_namespace import (
    BucketContext,
    S3ScopeContext,
    S3UserContext,
)
from tests.builders.s3_operations import S3Operations
from tests.factories.iscsi_client import IscsiClientFactory
from tests.factories.s3_user import ACTIVE_USER_QUOTA, TYPICAL_USER_QUOTA
from tests.support.package_setup import IntegrationPackage

DEFAULT_POOL_NAME = "nvme"


def destroy_if_exists(obj):
    existing = type(obj).query.filter_by(id=obj.id).first()
    if existing is not None:
        existing.destroy()


@dataclass
class CephAccountEnv:
    package: IntegrationPackage
    iscsi: object = field(init=False)
    s3: object = field(init=False)

    def __post_init__(self):
        self.iscsi = CephIscsiEnv(account=self)
        self.s3 = CephS3Env(account=self)

    @property
    def model(self):
        return self.package.account

    def __getattr__(self, name):
        return getattr(self.model, name)

    def track_by_id(self, items, obj):
        if not any(existing.id == obj.id for existing in items):
            items.append(obj)
        return obj

    def track_by_path(self, items, obj):
        if not any(existing.path == obj.path for existing in items):
            items.append(obj)
        return obj

    def cleanup(self):
        self.iscsi.cleanup()
        self.s3.cleanup()


@dataclass(init=False)
class CephIscsiEnv:
    account: CephAccountEnv
    _created_clients: list[object] = field(default_factory=list, init=False, repr=False)
    _created_disks: list[object] = field(default_factory=list, init=False, repr=False)

    def __init__(
        self,
        *,
        account: CephAccountEnv | None = None,
        package: IntegrationPackage | None = None,
    ):
        if account is None:
            if package is None:
                raise TypeError("CephIscsiEnv requires either 'account' or 'package'")
            account = CephAccountEnv(package=package)

        self.account = account
        self._created_clients = []
        self._created_disks = []

    @property
    def package(self):
        return self.account.package

    @property
    def account_model(self):
        return self.account.model

    @property
    def targets_by_pool(self):
        return self.package.targets_by_pool

    @property
    def quotas_by_pool(self):
        return self.package.iscsi_quotas_by_pool

    @property
    def scopes_by_pool(self):
        return {
            pool_name: self.scope(pool_name=pool_name)
            for pool_name in self.targets_by_pool
        }

    def scope(self, *, pool_name: str = DEFAULT_POOL_NAME):
        target = self.targets_by_pool[pool_name]
        quota = self.quotas_by_pool[pool_name]
        return IscsiScopeContext(
            account=self.account_model,
            cluster=target.cluster,
            quota=quota,
            target=target,
            pool_name=pool_name,
        )

    def scopes(self, *, pool_names: Iterable[str] | None = None):
        if pool_names is None:
            pool_names = self.targets_by_pool.keys()
        return [
            self.scope(pool_name=pool_name)
            for pool_name in pool_names
        ]

    def track_client(self, client):
        return self.account.track_by_id(self._created_clients, client)

    def track_disk(self, disk):
        return self.account.track_by_id(self._created_disks, disk)

    def cleanup(self):
        for disk in reversed(self._created_disks):
            destroy_if_exists(disk)
        for client in reversed(self._created_clients):
            destroy_if_exists(client)

        self._created_clients.clear()
        self._created_disks.clear()

    def client(self, **kwargs):
        client = IscsiClientFactory.create(account_id=self.account_model.id, **kwargs)
        return self.track_client(client)

    def clients(self, *, count: int, **kwargs):
        clients = [
            IscsiClientFactory.create(account_id=self.account_model.id, **kwargs)
            for _ in range(count)
        ]
        for client in clients:
            self.track_client(client)
        return clients

    def client_scope(self, **client_kwargs):
        client = self.client(**client_kwargs)
        return ClientContext(account=self.account_model, client=client)

    def disk(self, *, target, **kwargs):
        disk = IscsiOperations.create_ceph_disk(target=target, **kwargs)
        return self.track_disk(disk)

    def disks(self, *, target, count: int, **kwargs):
        disks = IscsiOperations.create_ceph_disks(target=target, count=count, **kwargs)
        for disk in disks:
            self.track_disk(disk)
        return disks

    def disk_scope(self, *, pool_name: str = DEFAULT_POOL_NAME, **disk_kwargs):
        scope = self.scope(pool_name=pool_name)
        disk = self.disk(target=scope.target, **disk_kwargs)
        return DiskContext(
            account=scope.account,
            cluster=scope.cluster,
            quota=scope.quota,
            target=scope.target,
            pool_name=scope.pool_name,
            disk=disk,
        )

    def assign(self, *, client, disks):
        return IscsiOperations.assign_ceph(client=client, disks=disks)


@dataclass(init=False)
class CephS3Env:
    account: CephAccountEnv
    _created_users: list[object] = field(default_factory=list, init=False, repr=False)
    _created_buckets: list[object] = field(default_factory=list, init=False, repr=False)

    def __init__(
        self,
        *,
        account: CephAccountEnv | None = None,
        package: IntegrationPackage | None = None,
    ):
        if account is None:
            if package is None:
                raise TypeError("CephS3Env requires either 'account' or 'package'")
            account = CephAccountEnv(package=package)

        self.account = account
        self._created_users = []
        self._created_buckets = []

    @property
    def package(self):
        return self.account.package

    @property
    def account_model(self):
        return self.account.model

    @property
    def quotas_by_pool(self):
        return self.package.s3_quotas_by_pool

    def scope(self, *, pool_name: str = DEFAULT_POOL_NAME):
        quota = self.quotas_by_pool[pool_name]
        return S3ScopeContext(
            account=self.account_model,
            quota=quota,
            pool_name=pool_name,
        )

    def track_user(self, s3_user):
        return self.account.track_by_id(self._created_users, s3_user)

    def track_bucket(self, bucket):
        return self.account.track_by_path(self._created_buckets, bucket)

    def cleanup(self):
        for bucket in reversed(self._created_buckets):
            S3Operations.delete_bucket(bucket)
        for s3_user in reversed(self._created_users):
            S3Operations.delete_user(s3_user)

        self._created_buckets.clear()
        self._created_users.clear()

    def user(
        self,
        *,
        pool_name: str = DEFAULT_POOL_NAME,
        quota=None,
        short_name: str | None = None,
        **kwargs,
    ):
        scope = self.scope(pool_name=pool_name)
        s3_user = S3Operations.create_user(
            account=self.account_model,
            pool=scope.quota.pool,
            account_quota=scope.quota,
            quota=quota if quota is not None else ACTIVE_USER_QUOTA.copy(),
            short_name=short_name,
            **kwargs,
        )
        return self.track_user(s3_user)

    def bucket(self, *, s3_user, **kwargs):
        bucket = S3Operations.create_bucket(s3_user=s3_user, **kwargs)
        return self.track_bucket(bucket)

    def user_scope(
        self,
        *,
        pool_name: str = DEFAULT_POOL_NAME,
        user_quota=None,
        **user_kwargs,
    ):
        scope = self.scope(pool_name=pool_name)
        s3_user = self.user(
            pool_name=pool_name,
            quota=user_quota,
            **user_kwargs,
        )
        return S3UserContext(
            account=self.account,
            quota=scope.quota,
            pool_name=scope.pool_name,
            user=s3_user,
        )

    def bucket_scope(
        self,
        *,
        pool_name: str = DEFAULT_POOL_NAME,
        user_quota=None,
        bucket_kwargs=None,
        **user_kwargs,
    ):
        bucket_kwargs = bucket_kwargs or {}
        user_ctx = self.user_scope(
            pool_name=pool_name,
            user_quota=user_quota or TYPICAL_USER_QUOTA,
            **user_kwargs,
        )
        bucket = self.bucket(s3_user=user_ctx.user, **bucket_kwargs)
        return BucketContext(
            account=user_ctx.account,
            quota=user_ctx.quota,
            pool_name=user_ctx.pool_name,
            user=user_ctx.user,
            bucket=bucket,
        )
