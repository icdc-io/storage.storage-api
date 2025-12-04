import pytest

from tests.factories.account import AccountFactory, get_all_accounts
from tests.factories.iscsi_cluster import IscsiClusterFactory
from tests.factories.iscsi_gateway import IscsiGatewayFactory
from tests.factories.iscsi_quota import IscsiQuotaFactory
from tests.factories.iscsi_targets import IscsiTargetFactory
from tests.factories.s3_quota import S3QuotaFactory


# Seed fixtures (package scope)
@pytest.fixture(scope="package")
def seed_operator():
    """Create base operator account for testing.

    This account is used for operator role tests throughout the suite.
    """
    AccountFactory.create(
        name="devel",
        description="Account for test operator role."
    )
    yield


@pytest.fixture(scope="package")
def seed_full_environment(env_data, seed_operator, iscsi_pools, s3_pools):
    """Seed complete test environment from configuration.

    Creates accounts, quotas, clusters, gateways, and targets
    based on env_data configuration.
    """
    for data in env_data.get("accounts", []):
        # Create account
        account = AccountFactory.create(name=data["name"])

        # Create S3 quotas
        for pool_name, quotas in data.get("s3", {}).get("quotas", {}).items():
            for quota in quotas:
                S3QuotaFactory.create(
                    account_id=account.id,
                    pool_id=s3_pools[pool_name].id,
                    **quota,
                )

        # Create iSCSI quotas
        for pool_name, quotas in data.get("iscsi", {}).get("quotas", {}).items():
            for quota in quotas:
                IscsiQuotaFactory.create(
                    account_id=account.id,
                    pool_id=iscsi_pools[pool_name].id,
                    **quota,
                )

        # Create iSCSI clusters with gateways and targets
        for cluster_data in data.get("iscsi", {}).get("clusters", []):
            cluster = IscsiClusterFactory.create(
                account_id=account.id,
                name=cluster_data["name"]
            )

            # Create gateways for cluster
            for gateway_data in cluster_data.get("gateways", []):
                IscsiGatewayFactory.create(
                    cluster_id=cluster.id,
                    **gateway_data
                )

            # Create targets for cluster
            for target_data in cluster_data.get("targets", []):
                IscsiTargetFactory.create(
                    cluster_id=cluster.id,
                    pool_id=iscsi_pools[target_data["pool_name"]].id,
                )

    yield


# Basic account fixtures
@pytest.fixture(scope="package")
def aqa():
    """Return the AQA test account.

    AQA account is pre-seeded and used for automated quality assurance tests.
    """
    accounts = get_all_accounts()
    aqa = next((acc for acc in accounts if acc.name == "aqa"), None)
    return aqa


@pytest.fixture(scope="function")
def account():
    """Create a single temporary account for testing."""
    return AccountFactory.create()


@pytest.fixture
def account_factory():
    """Factory to create multiple accounts.

    Args:
        count: Number of accounts to create (default: 1)
        **kwargs: Additional parameters to pass to AccountFactory

    Returns:
        Single account if count=1, list of accounts otherwise
    """
    def _create_accounts(count: int = 1, **kwargs):
        accounts = [
            AccountFactory.create(**kwargs)
            for _ in range(count)
        ]
        return accounts[0] if count == 1 else accounts

    return _create_accounts


@pytest.fixture(scope="function")
def get_accounts():
    """Retrieve all accounts from database.

    Returns:
        list: All account objects from database
    """
    return get_all_accounts()
