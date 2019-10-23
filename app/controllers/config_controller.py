"""
Config Controller
"""

from app.lib.request_utils import log, ok
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_gateway import IscsiGateways


def get_config_gateways(**kwargs):
    """
    Get the gateways for a given config ID.

    Args:
        **kwargs: Arbitrary keyword arguments.

    Returns:
        List: A list of serialized gateways.
    """

    config_id = kwargs["config_id"]
    return ok([i.serialize() for i in IscsiConfigs.get_by("id", config_id).gateways])


def set_config_gateway(**kwargs):
    """
    Set the configuration gateway with the provided parameters.

    Args:
        **kwargs: Arbitrary keyword arguments.

    Returns:
        Serialized gateway data in the form of a dictionary.
    """

    config_id, body = kwargs["config_id"], kwargs["body"]
    log.debug(f"Setting gateway to config {config_id} with params {body}")
    body["config_id"] = config_id
    gateway = IscsiGateways(**body)
    gateway.save()
    return ok(gateway.serialize())
