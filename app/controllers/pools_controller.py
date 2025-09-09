"""
Pools Controller
"""
from flask import jsonify, request
from marshmallow import ValidationError

from app.lib.request_utils import abort_detailed, parse_jsonapi_filters
from app.loggers import log
from app.models.pool import Pools, PoolSchema


def get_pools(subject):
    """
    Get pools based on the provided filter parameter.
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = PoolSchema(partial=True).load(parsed_filters)
    except ValidationError as e:
        abort_detailed(400, "Incorrect filter parameters", e.messages)

    pools = Pools.query.filter_by(**filters).all()
    log.debug(f"Filtered pools: {pools}")
    return jsonify(PoolSchema(many=True).dump(pools))
