from types import SimpleNamespace


def make_quota(
    *,
    data_size_gb=20,
    disks=10,
    usage_data_size_gb=0,
    usage_disks=1,
):
    return SimpleNamespace(
        data_size_gb=data_size_gb,
        disks=disks,
        compute_usage=lambda: {
            "data_size_gb": usage_data_size_gb,
            "disks": usage_disks,
        },
    )


def make_disk(
    *,
    disk_id=99,
    owner="user@example.com",
    size_gb=2,
    name="disk01",
    account_id=1,
    pool_id=1,
):
    return SimpleNamespace(
        id=disk_id,
        owner=owner,
        size_gb=size_gb,
        name=name,
        account_id=account_id,
        pool_id=pool_id,
    )
