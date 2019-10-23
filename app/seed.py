# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker

from app import consts
from app.loggers import log
# @DS: Importing is needed here for correct model queries in seeding
#      
from app.models import (  # noqa: E402
    account,
    iscsi_client,  # noqa: F401
    iscsi_config,  # noqa: F401
    iscsi_disk,  # noqa: F401
    iscsi_gateway,  # noqa: F401
    iscsi_quota,
    pool,
    s3_quota,
    s3_user,  # noqa: F401
    snapshot,  # noqa: F401
)
from app.models.account import Accounts
from app.models.pool import Pools
from app.models.s3_quota import S3Quotas
from app.models.iscsi_quota import IscsiQuotas

log.info("Imported seed module")

# Refactored function to seed the database with default data
def seed():
    """
    Seeds the database with default set of per-pool limits (aka LimitSet).

    There can be default LimitSet and default QuotaSet:
      - Default QuotaSet is assigned if S3/iSCSI quotas are not assigned during creation of account's resource partition.
      - Default LimitSet is a maximum value to which QuotaSet can be extended for any account account

    NOTE: Default QuotaSet currently is not implemented.

    Parameters:
        None

    Returns:
        None
    """
    log.info("Seeding default limits for pools")
    limits_account = Accounts.query.filter_by(name="default").first()
    log.info(f"Limits account: {limits_account}")
    if not limits_account:
        limits_account = Accounts(name="default", description="Default limits")
        limits_account.save()

    for pool_name, pool_data in consts.CEPH_POOL_S3.items():
        log.info(f"Initialize limits for S3 pool: {pool_name}")
        pool = Pools.query.filter_by(type="s3", name=pool_name).first()
        if not pool:
            log.info(f"Creating S3 pool: {pool_name}")
            pool = Pools(
                type="s3",
                name=pool_name,
                s3_placement_target=pool_name,
                klass=pool_name
            )
            pool.save()
        limits = S3Quotas.query.filter_by(pool_id = pool.id, account_id = limits_account.id).first()
        if not limits:
            log.debug(f"Creating limits for S3 pool: {pool_name}")
            limits = S3Quotas(
                pool_id = pool.id,
                account_id = limits_account.id,
                **pool_data["limits"]
            )
        else:
            log.debug(f"Updating limits for S3 pool: {pool_name}")
            limits.update(pool_data["limits"])
        limits.save()

    for pool_name, pool_data in consts.CEPH_POOL_ISCSI.items():
        log.info(f"Initialize limits for iSCSI pool: {pool_name}")
        pool = Pools.query.filter_by(type="iscsi", name=pool_name).first()
        if not pool:
            log.info(f"Creating iSCSI pool: {pool_name}")
            pool = Pools(
                type="iscsi",
                name=pool_name,
                klass=pool_name
            )
            pool.save()
        limits = IscsiQuotas.query.filter_by(pool_id = pool.id, account_id = limits_account.id).first()
        if not limits:
            log.debug(f"Creating limits for iSCSI pool: {pool_name}")
            limits = IscsiQuotas(
                pool_id = pool.id,
                account_id = limits_account.id,
                **pool_data["limits"]
            )
        else:
            log.debug(f"Updating limits for iSCSI pool: {pool_name}")
            limits.update(pool_data["limits"])
        limits.save()
