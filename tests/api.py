from typing import Optional, Tuple
from flask.testing import FlaskClient


class Api:
    def __init__(self, client: FlaskClient, prefix: str = "/api/v2"):
        self.client = client
        self.prefix = prefix

        self.s3 = _S3(self)

    def request(
        self,
        method: str,
        path: str,
        payload: dict,
        headers: dict,
    ) -> Tuple[object, Optional[dict]]:
        resp = self.client.open(self.prefix + path, method=method.upper(), json=payload, headers=headers)
        return resp.status_code, resp.get_json()

    def get(self, path, **kw):    return self.request("GET",    path, **kw)
    def post(self, path, **kw):   return self.request("POST",   path, **kw)
    def put(self, path, **kw):    return self.request("PUT",    path, **kw)
    def patch(self, path, **kw):  return self.request("PATCH",  path, **kw)
    def delete(self, path, **kw): return self.request("DELETE", path, **kw)


def _join(a: str, b: str | int) -> str:
    if not b:
        return a
    return f"{a.rstrip('/')}/{str(b).lstrip('/')}"


class _S3:
    def __init__(self, api: Api):
        self.api = api
        self.users = _S3Users(api)
        self.quotas = _S3Quotas(api)
        self.buckets = _Buckets(api)


class _S3Users:
    route = "/s3/users"

    def __init__(self, api: Api):
        self.api = api

    def create(self, payload: dict, hdr: dict):
        return self.api.post(self.route, payload=payload, headers=hdr)

    def get(self, user_id: int | str, **hdr):
        return self.api.get(_join(self.route, user_id), headers=hdr)

    def update(self, user_id: int | str, payload: dict, hdr: dict):
        return self.api.put(_join(self.route, user_id), payload=payload, headers=hdr)

    def delete(self, user_id: int | str, **hdr):
        return self.api.delete(_join(self.route, user_id), headers=hdr)


class _S3Quotas:
    route = "/s3/quotas"

    def __init__(self, api: Api):
        self.api = api

    def create(self, payload: dict, hdr: dict):
        return self.api.post(self.route, payload=payload, headers=hdr)

    def get(self, user_id: int | str, **hdr):
        return self.api.get(_join(self.route, user_id), headers=hdr)

    def update(self, user_id: int | str, payload: dict, hdr: dict):
        return self.api.put(_join(self.route, user_id), payload=payload, headers=hdr)

    def delete(self, user_id: int | str, **hdr):
        return self.api.delete(_join(self.route, user_id), headers=hdr)


class _Buckets:
    route = "/s3/buckets"

    def __init__(self, api: Api):
        self.api = api

    def create(self, payload: dict, hdr: dict):
        return self.api.post(self.route, payload=payload, headers=hdr)

    def get(self, user_id: int | str, **hdr):
        return self.api.get(_join(self.route, user_id), headers=hdr)

    def update(self, user_id: int | str, payload: dict, hdr: dict):
        return self.api.put(_join(self.route, user_id), payload=payload, headers=hdr)

    def delete(self, user_id: int | str, **hdr):
        return self.api.delete(_join(self.route, user_id), headers=hdr)
