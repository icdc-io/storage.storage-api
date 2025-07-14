"""
Gateway Controller
"""
from flask import request

from app.lib.controller_utils import trytest
from app.lib.request_utils import created, log, not_found, ok, request_json
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_gateway import IscsiGateways


def get_gateway(subject, gateway_id):
    """
    Retrive gateway information
    """
    gateway_obj = IscsiGateways.get_by("id", gateway_id)
    if gateway_obj is None:
        return not_found()
    return ok(gateway_obj.serialize())


def set_gateway(subject):
    """
    Set Gateway params
    """
    body = request_json(request)
    log.debug(f"Setting gateway with params {body}")
    config_obj = IscsiConfigs.get_by("id", body["config_id"])
    if config_obj is None:
        return not_found("Config with such ID does not exists")
    gateway_obj = IscsiGateways(**body)
    gateway_obj.save()
    return created(gateway_obj.serialize())
