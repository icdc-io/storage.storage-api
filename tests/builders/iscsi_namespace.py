from dataclasses import dataclass, field
from typing import Iterable

from tests.builders.account_namespace import AccountEnv, ScopeGuard, load_pools
from tests.builders.iscsi_operations import IscsiOperations
from tests.factories.iscsi_client import IscsiClientFactory
from tests.factories.iscsi_cluster import IscsiClusterFactory
from tests.factories.iscsi_disk import IscsiDiskFactory
from tests.factories.iscsi_gateway import IscsiGatewayFactory
from tests.factories.iscsi_quota import IscsiQuotaFactory
from tests.factories.iscsi_targets import IscsiTargetFactory

DEFAULT_POOL_NAME = "nvme"


@dataclass
class ClientContext:
    account: object
    client: object


@dataclass
class IscsiScopeContext:
    account: object
    cluster: object
    quota: object
    target: object
    pool_name: str


@dataclass
class DiskContext:
    account: object
    cluster: object
    quota: object
    target: object
    pool_name: str
    disk: object


@dataclass
class IscsiEnv(AccountEnv, ScopeGuard):
    iscsi_pools: dict = field(default_factory=dict)
    _scope_keys: set[tuple[int, int]] = field(
        default_factory=set,
        init=False,
    )

    def __post_init__(self):
        if not self.iscsi_pools:
            self.iscsi_pools = load_pools("iscsi")

    def cluster(self, *, account, **kwargs):
        return IscsiClusterFactory.create(account_id=account.id, **kwargs)

    def clusters(self, *, account, count: int, **kwargs):
        return [
            IscsiClusterFactory.create(account_id=account.id, **kwargs)
            for _ in range(count)
        ]

    def quota(
        self,
        *,
        account,
        pool_name: str = DEFAULT_POOL_NAME,
        **kwargs,
    ):
        return IscsiQuotaFactory.create(
            account_id=account.id,
            pool_id=self.iscsi_pools[pool_name].id,
            **kwargs,
        )

    def quotas(self, *, account, pool_names: Iterable[str], **kwargs):
        return [
            self.quota(account=account, pool_name=pool_name, **kwargs)
            for pool_name in pool_names
        ]

    def target(self, *, cluster, pool_name: str = DEFAULT_POOL_NAME, **kwargs):
        return IscsiTargetFactory.create(
            cluster_id=cluster.id,
            pool_id=self.iscsi_pools[pool_name].id,
        )

    def targets(self, *, cluster, pool_names: Iterable[str], **kwargs):
        return [
            self.target(cluster=cluster, pool_name=pool_name, **kwargs)
            for pool_name in pool_names
        ]

    def disk(self, *, target, **kwargs):
        return IscsiDiskFactory.create(target_id=target.id, **kwargs)

    def disks(self, *, target, count: int, **kwargs):
        return [
            self.disk(target=target, **kwargs)
            for _ in range(count)
        ]

    def gateway(self, *, cluster, **kwargs):
        return IscsiGatewayFactory.create(cluster_id=cluster.id, **kwargs)

    def gateways(self, *, cluster, count: int, **kwargs):
        return [
            self.gateway(cluster=cluster, **kwargs)
            for _ in range(count)
        ]

    def client(self, *, account, **kwargs):
        return IscsiClientFactory.create(account_id=account.id, **kwargs)

    def clients(self, *, account, count: int, **kwargs):
        return [
            self.client(account=account, **kwargs)
            for _ in range(count)
        ]

    def client_scope(self, *, account=None, **account_kwargs):
        account = account or self.account(**account_kwargs)
        client = self.client(account=account)
        return ClientContext(account=account, client=client)

    def scope(
        self,
        *,
        account=None,
        pool_name: str = DEFAULT_POOL_NAME,
        cluster=None,
        **quota_kwargs,
    ):
        if account is not None and cluster is not None:
            raise ValueError("Pass either account or cluster, not both.")
        if cluster is not None:
            account = cluster.account
        account = account or self.account()

        pool = self.iscsi_pools[pool_name]
        self._register_scope(
            kind="iSCSI",
            account=account,
            pool_name=pool_name,
            pool=pool,
            keys=self._scope_keys,
        )
        cluster = cluster or self.cluster(account=account)
        quota = self.quota(
            account=account,
            pool_name=pool_name,
            **quota_kwargs,
        )
        target = self.target(
            cluster=cluster,
            pool_name=pool_name,
        )
        return IscsiScopeContext(
            account=account,
            cluster=cluster,
            quota=quota,
            target=target,
            pool_name=pool_name,
        )

    def disk_scope(
        self,
        *,
        account=None,
        pool_name: str = DEFAULT_POOL_NAME,
        cluster=None,
        **disk_kwargs,
    ):
        scope = self.scope(
            account=account,
            pool_name=pool_name,
            cluster=cluster,
        )
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
        return IscsiOperations.assign_db(client=client, disks=disks)
