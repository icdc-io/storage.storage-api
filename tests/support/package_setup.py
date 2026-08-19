import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select

from app.database import db
from app.models.pool import Pools
from tests.factories.account import AccountFactory
from tests.factories.iscsi_cluster import IscsiClusterFactory
from tests.factories.iscsi_gateway import IscsiGatewayFactory
from tests.factories.iscsi_quota import IscsiQuotaFactory
from tests.factories.iscsi_targets import IscsiTargetFactory
from tests.factories.s3_quota import S3QuotaFactory


@dataclass
class IntegrationPackage:
    account: object
    targets_by_pool: dict[str, object]
    iscsi_quotas_by_pool: dict[str, object]
    s3_quotas_by_pool: dict[str, object]


def get_environment_data(filename: str = "config/fixtures_file.yaml") -> dict:
    env_file = os.getenv("FIXTURES_FILE")
    path = Path(env_file or filename)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_operator_account():
    AccountFactory.create(
        name="devel",
        description="Account for test operator role.",
    )


def pools_by_type(pool_type):
    stmt = select(Pools).where(Pools.type == pool_type)
    return {
        pool.klass: pool
        for pool in db.session.scalars(stmt)
    }


def create_configured_environment():
    env_data = get_environment_data()
    s3_pools = pools_by_type("s3")
    iscsi_pools = pools_by_type("iscsi")
    integration_package = None

    for data in env_data.get("accounts", []):
        account = AccountFactory.create(name=data["name"])
        targets_by_pool = {}
        iscsi_quotas_by_pool = {}
        s3_quotas_by_pool = {}

        for pool_name, quotas in data.get("s3", {}).get("quotas", {}).items():
            for quota in quotas:
                created_quota = S3QuotaFactory.create(
                    account_id=account.id,
                    pool_id=s3_pools[pool_name].id,
                    **quota,
                )
                s3_quotas_by_pool[pool_name] = created_quota

        for pool_name, quotas in data.get("iscsi", {}).get("quotas", {}).items():
            for quota in quotas:
                created_quota = IscsiQuotaFactory.create(
                    account_id=account.id,
                    pool_id=iscsi_pools[pool_name].id,
                    **quota,
                )
                iscsi_quotas_by_pool[pool_name] = created_quota

        for cluster_data in data.get("iscsi", {}).get("clusters", []):
            cluster = IscsiClusterFactory.create(
                account_id=account.id,
                name=cluster_data["name"],
            )

            for gateway_data in cluster_data.get("gateways", []):
                IscsiGatewayFactory.create(
                    cluster_id=cluster.id,
                    **gateway_data,
                )

            for target_data in cluster_data.get("targets", []):
                pool_name = target_data["pool_name"]
                target = IscsiTargetFactory.create(
                    cluster_id=cluster.id,
                    pool_id=iscsi_pools[pool_name].id,
                )
                targets_by_pool[pool_name] = target

        if integration_package is None:
            integration_package = IntegrationPackage(
                account=account,
                targets_by_pool=targets_by_pool,
                iscsi_quotas_by_pool=iscsi_quotas_by_pool,
                s3_quotas_by_pool=s3_quotas_by_pool,
            )

    if integration_package is None:
        raise RuntimeError("No configured integration account was created.")

    return integration_package


def setup_api_package(make_connection):
    conn, cleanup = make_connection.start_connection()
    try:
        create_operator_account()
        yield conn
    finally:
        cleanup()


def setup_integration_package(make_connection):
    conn, cleanup = make_connection.start_connection()
    try:
        create_operator_account()
        yield create_configured_environment()
    finally:
        cleanup()
