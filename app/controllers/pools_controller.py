"""
Pools Controller
"""
from flask import request, jsonify

from app.lib.request_utils import parse_jsonapi_filters, abort_detailed
from app.loggers import log
from app.models.pool import Pools, PoolSchema
from marshmallow import ValidationError


def get_pools(subject):
    """
    Get pools based on the provided filter parameter.
    """
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = PoolSchema(partial=True).load(parsed_filters)
    except ValidationError as e:
        abort_detailed(400, "Incorrect filter parameters.", e.messages)

    pools = Pools.query.filter_by(**filters).all()
    log.debug(f"Filtered pools: {pools}")
    return jsonify(PoolSchema(many=True).dump(pools))
