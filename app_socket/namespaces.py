from threading import Lock

from flask import request
from flask_socketio import Namespace, emit

from app_socket.config import WS_STATS_INTERVAL, log
from app_socket.metrics import collect_all_stats, filter_disk_stats, send_disk_stats
from app_socket.utils import parse_disks, parse_disks_from_args

# Thread safety and subscription tracking
thread = None
thread_lock = Lock()
# sid -> list of image names the client asked for
subscriptions = {}


def _get_socketio():
    from app_socket_server import socketio  # Avoid circular imports

    return socketio


def _disks_from_payload(data):
    """Clients may send `{"disks": ...}`, a bare list or a bare string."""
    return parse_disks(data.get("disks") if isinstance(data, dict) else data)


def _push_stats(socketio, sid, disks):
    """Send a single stats frame to one client."""
    socketio.emit("disk_stats_response", send_disk_stats(disks), to=sid)


# Background task that keeps every subscriber supplied with fresh stats
def stats_broadcast_thread(socketio):
    """Poll Prometheus once per interval and fan the result out to subscribers.

    Polling once per tick rather than once per client keeps the load on
    Prometheus independent of how many clients are connected.
    """
    while True:
        socketio.sleep(WS_STATS_INTERVAL)

        if not any(subscriptions.values()):
            continue

        stats = collect_all_stats()
        for sid, disks in list(subscriptions.items()):
            if not disks:
                continue
            socketio.emit(
                "disk_stats_response", filter_disk_stats(stats, disks), to=sid
            )


# WebSocket Namespace for disk statistics
class SendStatNamespace(Namespace):
    def on_connect(self):
        global thread
        socketio = _get_socketio()
        disks = parse_disks_from_args(request.args)
        subscriptions[request.sid] = disks

        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(
                    stats_broadcast_thread, socketio
                )

        log.info(f"Client connected: {request.sid}, disks: {disks}")
        emit("response", {"data": "Connected"})

        # Deliver a first frame without waiting out a full interval. Runs in the
        # background so a slow Prometheus cannot hold up the handshake.
        if disks:
            socketio.start_background_task(_push_stats, socketio, request.sid, disks)

    def on_disconnect(self, reason=None):
        subscriptions.pop(request.sid, None)
        log.info(f"Client disconnected: {request.sid} ({reason})")

    def on_my_ping(self):
        emit("pong")

    def on_subscribe(self, data):
        """Replace the client's disk list without reconnecting."""
        socketio = _get_socketio()
        disks = _disks_from_payload(data)
        subscriptions[request.sid] = disks
        log.info(f"Client {request.sid} subscribed to: {disks}")

        if disks:
            socketio.start_background_task(_push_stats, socketio, request.sid, disks)

    def on_send_stats(self, data):
        """One-off request, kept for clients that poll instead of subscribing."""
        disks = _disks_from_payload(data) or subscriptions.get(request.sid, [])
        emit("disk_stats_response", send_disk_stats(disks))
