from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from flask.testing import FlaskClient


def _join(a: str, b: Any | None) -> str:
    """Join URL parts safely, ignoring None."""
    return f"{a.rstrip('/')}/{str(b).lstrip('/')}" if b is not None else a


class Api:
    """Wrapper for Flask test client with grouped endpoints."""

    def __init__(self, client: FlaskClient, prefix: str = "/api/v2"):
        self.client = client
        self.prefix = prefix
        self.s3 = _S3(self)
        self.iscsi = _Iscsi(self)

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[dict] = None,
        header: Optional[Dict[str, Any]] = None,
        *,
        hdr: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[dict]]:
        """Send HTTP request and return (status_code, json)."""
        if header is None and hdr is not None:
            header = hdr

        resp = self.client.open(
            self.prefix + path,
            method=method.upper(),
            json=payload,
            headers=header,
            query_string=query,
        )
        # 204 → no JSON body — get_json() returns None
        return resp.status_code, resp.get_json(silent=True)


@dataclass
class Resource:
    """Generic CRUD resource bound to API route."""
    api: Api
    route: str

    def _call(
        self,
        method: str,
        suffix: Any | None = None,
        payload: Optional[dict] = None,
        header: Optional[Dict[str, Any]] = None,
        *,
        hdr: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[dict]]:
        """Internal unified request helper."""
        return self.api.request(
            method,
            _join(self.route, suffix),
            payload=payload,
            header=header,
            hdr=hdr,
            query=query,
        )

    def create(self, payload: dict, header: Optional[Dict[str, Any]] = None, **kw):
        """POST /resource"""
        return self._call("POST", payload=payload, header=header, **kw)

    def get(self, obj_id: Any, header: Optional[Dict[str, Any]] = None, **kw):
        """GET /resource/{id}"""
        return self._call("GET", suffix=obj_id, header=header, **kw)

    def update(self, obj_id: Any, payload: dict, header: Optional[Dict[str, Any]] = None, **kw):
        """PUT /resource/{id}"""
        return self._call("PUT", suffix=obj_id, payload=payload, header=header, **kw)

    def delete(self, obj_id: Any, header: Optional[Dict[str, Any]] = None, **kw):
        """DELETE /resource/{id}"""
        return self._call("DELETE", suffix=obj_id, header=header, **kw)

    def list(self, query: Optional[Dict[str, Any]] = None, header: Optional[Dict[str, Any]] = None, **kw):
        """GET /resource (list with optional filters)."""
        return self._call("GET", header=header, query=_to_filter_query(query), **kw)


def _to_filter_query(query: dict | None):
    """Convert dict to 'filter[key]' query params."""
    if not query:
        return None
    out = {}
    for k, v in query.items():
        if v is None:
            continue
        sk = str(k)
        fk = sk if sk.startswith("filter[") else f"filter[{sk}]"
        out[fk] = v
    return out


class _Iscsi:
    """Group of iSCSI resources."""
    def __init__(self, api: Api):
        self.clusters = Resource(api, "/iscsi/clusters")
        self.targets = Resource(api, "/iscsi/targets")
        self.gateways = Resource(api, "/iscsi/gateways")
        self.quotas = Resource(api, "/iscsi/quotas")
        self.disks = Resource(api, "/iscsi/disks")


class _S3:
    """Group of S3 resources."""
    def __init__(self, api: Api):
        self.users = Resource(api, "/s3/users")
        self.quotas = Resource(api, "/s3/quotas")
        self.buckets = Resource(api, "/s3/buckets")
