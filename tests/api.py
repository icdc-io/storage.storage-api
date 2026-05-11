from __future__ import annotations

import inspect
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

    def _get_caller_markers(self) -> list:
        """Retrieve pytest markers from the calling test function.

        Walks up the call stack to find the test function that invoked
        this method and extracts its pytest markers.

        Returns:
            list: List of pytest marker objects, empty list if no markers found
        """
        for frame_info in inspect.stack():
            func_name = frame_info.function

            # Look for test function (starts with 'test_')
            if func_name.startswith('test_'):
                frame_globals = frame_info.frame.f_globals

                if func_name in frame_globals:
                    test_func = frame_globals[func_name]
                    markers = getattr(test_func, 'pytestmark', [])

                    # Normalize to list format
                    if not isinstance(markers, list):
                        markers = [markers] if markers else []

                    return markers

        return []

    def _has_marker(self, marker_name: str) -> bool:
        """Check if the calling test has a specific pytest marker.

        Args:
            marker_name: Name of the marker to check (e.g., "ceph", "slow")

        Returns:
            bool: True if marker is present, False otherwise
        """
        markers = self._get_caller_markers()
        return any(marker.name == marker_name for marker in markers)

    def _should_use_real_ceph(self) -> bool:
        """Determine if real Ceph storage should be used.

        Returns:
            bool: True if test has @pytest.mark.ceph, False otherwise
        """
        return self._has_marker("ceph")

    def _correct_payload(self, payload):
        if not isinstance(payload, dict):
            return payload
        return {k: v for k, v in payload.items() if v is not None}

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

        # Add fake flag based on test marker
        if not self._should_use_real_ceph():
            header["X-Fake-Ceph"] = True

        payload = self._correct_payload(payload)

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


class ClientsResource(Resource):
    """Extended Resource for /iscsi/clients including nested actions."""

    def assign(self, client_id: Any, payload: dict, header=None, *, hdr=None, query=None):
        """POST /iscsi/clients/{client_id}/assign"""
        return self._call(
            "POST",
            suffix=f"{client_id}/disks",
            payload=payload,
            header=header,
            hdr=hdr,
            query=query,
        )

    def unassign(self, client_id: Any, disk_id: Any, header=None, *, hdr=None, query=None):
        """POST /iscsi/clients/{client_id}/assign"""
        return self._call(
            "DELETE",
            suffix=f"{client_id}/disks/{disk_id}",
            header=header,
            hdr=hdr,
            query=query,
        )


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
        self.clients = Resource(api, "/iscsi/clients")

        self.client_disks = ClientsResource(api, "/iscsi/clients")


class _S3:
    """Group of S3 resources."""
    def __init__(self, api: Api):
        self.users = Resource(api, "/s3/users")
        self.quotas = Resource(api, "/s3/quotas")
        self.buckets = Resource(api, "/s3/buckets")
