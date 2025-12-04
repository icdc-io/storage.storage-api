import pytest

from tests.factories.iscsi_quota import IscsiQuotaFactory, get_limitset


@pytest.fixture
def get_pool_limitset():
    """Retrieve quota limits for a specific pool.

    Args:
        pool_id: ID of the pool to get limits for

    Returns:
        dict: Quota limit settings for the pool
    """
    def _get(pool_id):
        return get_limitset(pool_id)

    return _get


@pytest.fixture(scope="function")
def iscsi_quota(account, iscsi_pools):
    """Create a single default iSCSI quota for the given account (nvme pool)."""
    return IscsiQuotaFactory.create(
        account_id=account.id,
        pool_id=iscsi_pools["nvme"].id,
        default=True,
    )


@pytest.fixture
def iscsi_quota_factory(account_factory, iscsi_pools):
    """Factory to create one or multiple iSCSI quotas.

    Args:
        account: Account to create quotas for. If omitted, a new account is created.
        quota_pools: Pool name or list of pool names (default: "nvme").
        **kwargs: Extra params for IscsiQuotaFactory (max_size_gb, max_iops, etc.).

    Returns:
        Single quota if one pool, otherwise list of quotas.
    """
    def _create_quotas(account=None, quota_pools="nvme", **kwargs):
        account = account or account_factory()
        pool_names = _normalize_pools(quota_pools)

        quotas = [
            IscsiQuotaFactory.create(
                account_id=account.id,
                pool_id=iscsi_pools[pool_name].id,
                **kwargs,
            )
            for pool_name in pool_names
        ]

        return quotas[0] if len(quotas) == 1 else quotas

    def _normalize_pools(pools):
        """Normalize pools argument to a list."""
        if pools is None:
            return ["nvme"]
        return [pools] if isinstance(pools, str) else pools

    return _create_quotas
