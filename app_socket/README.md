# Disk Stats WebSocket Service

Flask-SocketIO service that streams per-image iSCSI disk statistics collected from
Ceph's Prometheus exporter. It runs as a **separate process** from the REST API,
though both share the same image.

## Project structure

| File | Purpose |
| --- | --- |
| `../app_socket_server.py` | Entry point: Flask app, `SocketIO` instance, namespace registration |
| `namespaces.py` | Connection handling, subscriptions, background broadcast task |
| `metrics.py` | Prometheus polling and parsing |
| `utils.py` | Metric name mapping and `disks` payload parsing |
| `config.py` | Constants pulled from `app.consts` |
| `for_test.py` | Manual smoke test client |
| `ws-connection-example.html` | Manual smoke test page |

## Endpoint contract

- **engine.io path**: `/ws/disk_stats` (configurable, see below)
- **namespace**: default (`/`) — routing is done by path, not by namespace

The path must match on all three sides: the `path` option of the socket.io client,
the nginx location that proxies to this service, and `WS_PATH` here. nginx forwards
`$request_uri` unchanged, so it cannot paper over a mismatch.

### Events sent by the server

| Event | Payload | When |
| --- | --- | --- |
| `response` | `{"data": "Connected"}` | On connect |
| `disk_stats_response` | `{"<pool>/<image>": {"read_iops": ..., "read_throughput_mb": ..., "write_iops": ..., "write_throughput_mb": ...}}` | Every `WS_STATS_INTERVAL` seconds, plus once right after connect/subscribe |
| `pong` | — | In reply to `my_ping` |

### Events accepted by the server

| Event | Payload | Purpose |
| --- | --- | --- |
| `subscribe` | `{"disks": "a,b"}` or `{"disks": ["a", "b"]}` | Replace the disk list without reconnecting |
| `send_stats` | same as above, optional | One-off request, for clients that prefer polling |
| `my_ping` | — | Connectivity check |

The initial disk list is taken from the connection query string, so a client that
only wants the stream does not have to emit anything at all.

## Disk identifier format

The server expects disk identifiers exactly as they appear in Prometheus metrics:
`<pool>/<image>`, where `<pool>` is `{pool.type}-{pool.class}` and `<image>` is
`{account_name}_{disk.name}`.

Example: `iscsi-nvme/uzhst_march`.

If a disk name does not match this format, the server will return `{}` for that
request (no translation or account scoping is performed). Subscriptions with
incorrect names will silently receive no stats for them.

## Configuration

Values come from `settings/config.yaml` and can be overridden by environment
variables of the same (uppercased) name — see `app/consts.py`.

| Variable | Default | Notes |
| --- | --- | --- |
| `WS_PATH` | `/ws/disk_stats` | engine.io path |
| `WS_STATS_INTERVAL` | `10` | Seconds between pushes |
| `CEPH_HOST` | *(empty)* | **Required.** Without it `CEPH_PROMETHEUS_HOST` resolves to `None:9285` and every response is `{}` |
| `CEPH_PROMETHEUS_HOST` | `{CEPH_HOST}:9285` | Set directly if the exporter is not on the Ceph VIP |
| `LOG_LEVEL` | `DEBUG` | |

## Running

```bash
pip install -r ../requirements.txt
CEPH_HOST=<ceph-vip> gunicorn -c app_socket/gunicorn.conf.py app_socket_server:app
```

Run from the repository root — `app.consts` reads `settings/config.yaml` relative to
the working directory.

The default worker class is `eventlet`; the plain sync worker cannot serve WebSocket
connections. If eventlet turns out to be a problem, `gevent-websocket` is also in
`requirements.txt` and provides
`geventwebsocket.gunicorn.workers.GeventWebSocketWorker`.

For a quick local check without a client:

```bash
curl -i "http://localhost:8080/ws/disk_stats/?EIO=4&transport=polling"
```

A `200` with a body starting `0{"sid":` means the endpoint is wired correctly; a
`404` means the path does not match.

## Deployment notes

The image's default `CMD` starts the REST API, so the WebSocket Deployment has to
override the command:

```
command: ["gunicorn", "-c", "app_socket/gunicorn.conf.py", "app_socket_server:app"]
env:
  - name: SKIP_MIGRATIONS
    value: "1"
```

`SKIP_MIGRATIONS=1` keeps this pod from racing the API pod on `flask db upgrade`.

Keep `replicas: 1`. Subscriptions live in process memory, so scaling out requires
configuring a message queue (Redis) for Flask-SocketIO first.

On the nginx side, raise `proxy_read_timeout` / `proxy_send_timeout` (the 60s default
is only survived thanks to engine.io pings). The hardcoded `Connection "Upgrade"`
header is fine only while clients connect with `transports: ["websocket"]`; it breaks
the HTTP polling fallback.

## Known gaps

- **No authentication or authorization.** `cors_allowed_origins` is `"*"` and any
  client can request statistics for an arbitrary image name, with no account
  scoping — unlike the REST API, which goes through `flask-rbac-icdc`.
- `app/consts.py` logs every uppercase constant at INFO on startup, including
  `DATABASE_PASSWORD`. That output lands in this service's logs too.
- There is no automated test coverage for `app_socket`; `pyproject.toml` measures
  coverage for `app` only.
