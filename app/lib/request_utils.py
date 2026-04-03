"""Small helper function used all around the code"""

import json
import logging as log
import sys
from enum import StrEnum

from flask import abort, jsonify, request

from app import consts

log.basicConfig(
    stream=sys.stdout,
    level=getattr(log, consts.LOG_LEVEL, "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class HttpMethod(StrEnum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"


def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    response = e.get_response()
    data = {"status": e.code, "message": f"{e.description}"}
    if response.json:
        data = data | response.json
    response.data = json.dumps(data)
    response.content_type = "application/json"
    return response


def abort_detailed(code, message, errors):
    response = jsonify({"errors": format_validation_errors(errors)})
    response.status_code = code
    abort(code, message, response)


def format_validation_errors(errors: any) -> list[str]:
    errors_list = []

    if isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, (list, tuple)):
                for msg in messages:
                    errors_list.append(f"{field}: {msg}")
            else:
                errors_list.append(f"{field}: {messages}")
    elif isinstance(errors, str):
        errors_list.append(errors)
    elif isinstance(errors, list):
        for msg in errors:
            errors_list.append(str(msg))
    else:
        errors_list.append(str(errors))

    return errors_list


def parse_jsonapi_filters(args: dict) -> dict:
    """Parse args dictionary in JSON:API format for filters"""
    filters = {"base": {}}

    for key, value in args.items():
        if not (key.startswith("filter[") and key.endswith("]")):
            continue
        field_name = key[7:-1]

        if "." in field_name:
            relation, attr = field_name.split(".", 1)
            filters.setdefault(relation, {})[attr] = value
        else:
            filters["base"][field_name] = value

    return filters

def is_fake() -> bool:
    """
    Determines whether Ceph calls should be skipped.

    Logic:
    - If the request contains the header `X-Fake-Ceph` with a truthy value
      (true / yes / 1, case-insensitive), the request is treated as a fake-run
      and no real Ceph operations will be performed.
    - Otherwise, Ceph calls will be executed normally.
    """
    fake_header = "X-Fake-Ceph"
    header_val = request.headers.get(fake_header)

    if header_val is None:
        return False

    return header_val.lower() in ("1", "true", "yes")


def dig(self, *keys):
    """Ruby's hash.dig() implementation"""
    for key in keys:
        if not isinstance(self, dict):
            break
        self = self.get(key)
    return self


def is_failed(response)->bool:
    """
    Status code >= 400
    """
    if "code" in response and 400 <= response["code"]:
        return True
    return False


def ok(data=None):
    """
    Status code 200
    """
    return {"code": 200, "data": data}


def created(data=None):
    """
    Status code 201
    """
    return {"code": 201, "data": data}


def no_content(data=None):
    """
    Status code 204
    """
    return {"code": 204, "data": data}


def bad_request(data=None):
    """
    Status code 400
    """
    return {"code": 400, "data": data}


def unauthorized(data=None):
    """
    Status code 401
    """
    return {"code": 401, "data": data}


def forbidden(data=None):
    """
    Status code 403
    """
    return {"code": 403, "data": data}


def not_found(data=None):
    """
    Status code 404
    """
    return {"code": 404, "data": data}


def method_not_allowed(data=None):
    """
    Status code 405
    """
    return {"code": 405, "data": data}


def conflict(data=None):
    """
    Status code 409
    """
    return {"code": 409, "data": data}


def unprocessable_entity(data=None):
    """
    Status code 422
    """
    return {"code": 422, "data": data}


def internal_server_error(data=None):
    """
    Status code 500
    """
    return {"code": 500, "data": data}


def not_implemented(data=None):
    """
    Status code 501
    """
    return {"code": 501, "data": data}


def bad_gateway(data=None):
    """
    Status code 502
    """
    return {"code": 502, "data": data}


def gateway_timeout(data=None):
    """
    Status code 504
    """
    return {"code": 504, "data": data}


def process_response(response):
    """
    Status code 200
    """
    if response is None or not isinstance(response, dict) or len(response) == 0:
        log.error("Failed to process the response from the controller")
        return abort(500)
    try:
        code = int(response["code"])
        data = response["data"]
        return jsonify(data), code
    except (KeyError, ValueError):
        return abort(500)
    except TypeError:
        return jsonify({}), code


def request_json(request):
    """
    Define request body
    """
    try:
        data = request.get_json()
        if data is None:
            abort(400, "Unable to process request body")
        return data
    except json.decoder.JSONDecodeError:
        abort(400, "Unable to process request body")


def query(request):
    """
    Define query params
    """
    return dict(request.args)


status_codes = {
    200: ok,
    201: created,
    204: no_content,
    400: bad_request,
    401: unauthorized,
    403: forbidden,
    404: not_found,
    405: method_not_allowed,
    409: conflict,
    422: unprocessable_entity,
    500: internal_server_error,
    501: not_implemented,
    502: bad_gateway,
    504: gateway_timeout,
}
