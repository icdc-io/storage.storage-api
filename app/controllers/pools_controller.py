"""
Pools Controller
"""
from flask import abort, jsonify, request
from marshmallow import ValidationError

from app.lib.request_utils import parse_jsonapi_filters
from app.loggers import log
from app.models.pool import Pools, PoolSchema


def get_pools(subject):
    """
    Get pools based on the provided filter parameter.
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        pools = Pools.filtered(subject, request_filters=parsed_filters).all()
    except ValidationError as e:
        abort(400, e.messages)
    log.debug(f"Filtered pools: {pools}")
    return jsonify(PoolSchema(many=True).dump(pools))
