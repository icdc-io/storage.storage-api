from app import consts
from app.loggers import log

# Import models for correct queries during seeding
from app.models import (
    iscsi_client,  # noqa: F401
    iscsi_config,  # noqa: F401
    iscsi_disk,  # noqa: F401
    iscsi_gateway,  # noqa: F401
    s3_user,  # noqa: F401
    snapshot,  # noqa: F401
)
from app.models.account import Accounts
from app.models.iscsi_quota import IscsiQuotas
from app.models.pool import Pools
from app.models.s3_quota import S3Quotas

log.info("Imported seed module")


def get_or_create_account(name: str, description: str) -> Accounts:
    """
    Retrieve an account by name or create it if not found.

    :param name: The account name.
    :param description: A brief description of the account.
    :return: An Accounts instance.
    """
    account = Accounts.query.filter_by(name=name).first()
    if not account:
        log.info(f"Creating account: {name}")
        account = Accounts(name=name, description=description)
        account.save()
    return account


def get_or_create_pool(pool_type: str, name: str, **kwargs) -> Pools:
    """
    Retrieve a pool by type and name or create it if it does not exist.

    Additional parameters can be passed via kwargs.

    :param pool_type: The type of the pool (e.g., 's3' or 'iscsi').
    :param name: The pool name.
    :param kwargs: Additional attributes for pool creation.
    :return: A Pools instance.
    """
    pool = Pools.query.filter_by(type=pool_type, name=name).first()
    if not pool:
        log.info(f"Creating {pool_type.upper()} pool: {name}")
        pool = Pools(type=pool_type, name=name, **kwargs)
        pool.save()
    return pool


def create_or_update_quota(
    quota_model, pool: Pools, account: Accounts, limits_data: dict
):
    """
    Create or update quotas for the specified pool and account.

    :param quota_model: The quota model (e.g., S3Quotas or IscsiQuotas).
    :param pool: The pool instance.
    :param account: The account instance.
    :param limits_data: Dictionary containing limit values.
    """
    quota = quota_model.query.filter_by(pool_id=pool.id, account_id=account.id).first()
    if quota:
        log.debug(f"Updating limits for {quota_model.__name__} pool: {pool.name}")
        quota.update(limits_data)
    else:
        log.debug(f"Creating limits for {quota_model.__name__} pool: {pool.name}")
        quota = quota_model(pool_id=pool.id, account_id=account.id, **limits_data)
    quota.save()


def seed():
    """
    Seeds the database with default limits for pools.

    For each pool type (S3 and iSCSI), the function retrieves or creates a pool,
    then creates or updates the quotas associated with the default account.
    """
    log.info("Seeding default limits for pools")
    limits_account = get_or_create_account("default", "Default limits")
    log.info(f"Limits account: {limits_account}")

    # Process S3 pools
    for pool_name, pool_data in consts.CEPH_POOL_S3.items():
        log.info(f"Initializing limits for S3 pool: {pool_name}")
        pool_klass = pool_data.get("klass", pool_name)
        pool = get_or_create_pool(
            "s3", pool_name, klass=pool_klass
        )
        create_or_update_quota(S3Quotas, pool, limits_account, pool_data["limits"])

    # Process iSCSI pools
    for pool_name, pool_data in consts.CEPH_POOL_ISCSI.items():
        log.info(f"Initializing limits for iSCSI pool: {pool_name}")
        pool_klass = pool_data.get("klass", pool_name)
        pool = get_or_create_pool("iscsi", pool_name, klass=pool_klass)
        create_or_update_quota(
            IscsiQuotas, pool, limits_account, pool_data["limits"]
        )
