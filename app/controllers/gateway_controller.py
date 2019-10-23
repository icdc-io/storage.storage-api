"""
Gateway Controller
"""

from app.lib.controller_utils import trytest
from app.lib.request_utils import created, log, not_found, ok
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_gateway import IscsiGateways


@trytest
def get_gateway(**kwargs):
    """
    Retrive gateway information
    """
    gateway_id = kwargs["gateway_id"]
    gateway_obj = IscsiGateways.get_by("id", gateway_id)
    if gateway_obj is None:
        return not_found()
    return ok(gateway_obj.serialize())


def set_gateway(**kwargs):
    """
    Set Gateway params
    """
    body = kwargs["body"]
    log.debug(f"Setting gateway with params {kwargs}")
    config_obj = IscsiConfigs.get_by("id", body["config_id"])
    if config_obj is None:
        return not_found("Config with such ID does not exists")
    gateway_obj = IscsiGateways(**kwargs["body"])
    gateway_obj.save()
    return created(gateway_obj.serialize())
