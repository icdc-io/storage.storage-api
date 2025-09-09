from threading import Lock

from flask import request
from flask_socketio import Namespace, disconnect, emit

from app_socket.config import log
from app_socket.metrics import send_disk_stats

# Thread safety and connection tracking
thread = None
thread_lock = Lock()
connected_pool = []


# Background thread to send periodic messages to clients
def background_thread(socketio):
    """Example of how to send server-generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)  # Non-blocking sleep
        count += 1
        socketio.emit(
            "my_response",
            {"data": "Server generated event", "count": count},
            namespace="/ws/disk_stats",
        )


# WebSocket Namespace for disk statistics
class SendStatNamespace(Namespace):
    def on_connect(self):
        global thread
        global connected_pool
        with thread_lock:
            if request.sid not in connected_pool:
                connected_pool.append(request.sid)
            if thread is None:
                from app_socket_server import socketio  # Avoid circular imports

                thread = socketio.start_background_task(background_thread, socketio)
        log.info(f"Client connected: {request.sid}")
        emit("response", {"data": "Connected"})

    def on_disconnect(self):
        global connected_pool
        if request.sid in connected_pool:
            connected_pool.remove(request.sid)
        log.info(f"Client disconnected: {request.sid}")
        emit("response", {"data": "Disconnected"})
        disconnect(sid=request.sid)

    def on_my_ping(self):
        emit("pong")

    def on_send_stats(self, data):
        global connected_pool
        if request.sid in connected_pool:
            query = data.get("disks", "").split(",")
            if query:
                stats = send_disk_stats(query)
                emit("disk_stats_response", stats, room=request.sid)
