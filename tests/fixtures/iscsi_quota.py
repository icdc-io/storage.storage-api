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
    """Create a single default iSCSI quota for the given account.

    Uses nvme pool by default.
    """
    return IscsiQuotaFactory.create(
        account_id=account.id,
        pool_id=iscsi_pools["nvme"].id,
        default=True
    )


@pytest.fixture
def iscsi_quota_factory(account_factory, iscsi_pools):
    """Factory to create iSCSI quotas for accounts.

    Args:
        account: Account to create quotas for (auto-creates if not provided)
        quota_pools: Pool name or list of pool names (default: "nvme")
        **kwargs: Additional parameters (max_size_gb, max_iops, etc.)

    Returns:
        Single quota if one pool, list of quotas otherwise

    Usage:
        # Single quota in default nvme pool
        quota = iscsi_quota_factory(account)

        # Quotas in multiple pools
        quotas = iscsi_quota_factory(account, quota_pools=["nvme", "ssd"])

        # Custom quota with limits
        quota = iscsi_quota_factory(account, max_size_gb=500)

        # Auto-create account
        quota = iscsi_quota_factory(quota_pools="ssd")
    """
    def _create_quotas(account=None, quota_pools="nvme", **kwargs):
        # Auto-create account if not provided
        if not account:
            account = account_factory()

        # Normalize pool names to list
        pool_names = _normalize_pools(quota_pools)

        # Create quota for each pool
        quotas = [
            IscsiQuotaFactory.create(
                account_id=account.id,
                pool_id=iscsi_pools[pool_name].id,
                **kwargs
            )
            for pool_name in pool_names
        ]

        return quotas[0] if len(pool_names) == 1 else quotas

    def _normalize_pools(pools):
        """Convert pools parameter to list format."""
        if pools is None:
            return ["nvme"]
        return [pools] if isinstance(pools, str) else pools

    return _create_quotas
