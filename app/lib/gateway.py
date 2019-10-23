"""
Gateway module
"""

import json
import time

import requests

from app import consts
from app.controllers import auth
from app.lib import request_utils
from app.lib.request_utils import log

methods = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "PATCH": requests.patch,
    "DELETE": requests.delete,
}


def gateway(url, method, **kwargs):
    """
    Http/Https requests
    """
    method = methods.get(method, None)
    if method is None:
        return request_utils.not_implemented()
    start_t = time.time()
    try:
        resp = method(url, **kwargs)
    except requests.exceptions.Timeout as t_e:
        log.error(t_e, exc_info=True)
        return request_utils.gateway_timeout(
            {"error": "The connection to an upstream server timed out."}
        )
    except requests.exceptions.RequestException as r_e:
        log.error(r_e, exc_info=True)
        return request_utils.bad_gateway(
            {"error": "The connection to an upstream server timed out."}
        )
    except requests.exceptions.MissingSchema as m_e:
        log.error(m_e, exc_info=True)
        return request_utils.bad_request(
            {"error": "The connection to an upstream server timed out."}
        )
    except requests.exceptions.ConnectionError as c_e:
        log.error(c_e, exc_info=True)
        return request_utils.bad_gateway(
            {"error": "The connection to an upstream server timed out."}
        )
    log.info(f"{round(time.time() - start_t, 3)} s. - {resp.request.url}")
    if not resp.ok:
        try:
            data = resp.json()
        except json.decoder.JSONDecodeError:
            data = str(resp.content)
        return request_utils.bad_gateway({"error": data})
    return resp


def concat_url(base_url, uri):
    """
    Define uri
    """
    if uri.startswith(base_url):
        return uri
    return "{}{}{}".format(
        base_url
        if (base_url.startswith("https://") or base_url.startswith("http://"))
        else f"https://{base_url}",
        "/" if not base_url.endswith("/") else "",
        uri if not uri.startswith("/") else uri[1:],
    )
