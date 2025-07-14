"""
Config Controller
"""
from flask import abort, jsonify, request

from app.lib.request_utils import log, request_json
from app.models.iscsi_config import IscsiConfigs
from app.models.iscsi_gateway import IscsiGateways, IscsiGatewaySchema


def get_config_gateways(subject, config_id):
    """
    Get the gateways for a given config ID.
    """
    config = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config:
        abort(404, "Config with such id not found or you haven't permission.")

    return jsonify(IscsiGatewaySchema(many=True).dump(config.gateways))


def set_config_gateway(subject, config_id):
    """
    Set the configuration gateway with the provided parameters.
    """
    body = request_json(request)
    if IscsiConfigs.filtered(subject).filter_by(id=config_id).first():
        abort(404, "Config not found or you haven't permission.")

    log.debug(f"Setting gateway to config {config_id} with params {body}")
    gateway = IscsiGateways(**body)
    gateway.save()
    return IscsiGatewaySchema().dump(gateway)
