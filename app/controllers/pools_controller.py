"""
Pools Controller
"""

from app.lib.controller_utils import trytest
from app.lib.request_utils import ok
from app.loggers import log
from app.models.pool import Pools


@trytest
def get_pools(**kwargs):
    """
    Get pools based on the provided filter parameter.

    Args:
        **kwargs: keyword arguments to filter the pools.

    Returns:
        list: A list of filtered pools.
    """

    filter_param = kwargs["filter"]
    pools = Pools.query.all()
    filtered_pools = [i.serialize() for i in pools if i.type == filter_param["type"]]
    log.debug(f"Filtered pools: {filtered_pools}")
    return ok(filtered_pools)
