"""Manual smoke test for the disk stats WebSocket endpoint.

    python3 app_socket/for_test.py
    WS_URL=https://api.dcz.lab.icdc.io python3 app_socket/for_test.py

Connects the same way the frontend does: a socket.io client on the default
namespace, with the endpoint selected by `socketio_path`.
"""

import os
import time
from urllib.parse import urlencode

import socketio

WS_URL = os.getenv("WS_URL", "http://localhost:8080")
WS_PATH = os.getenv("WS_PATH", "/ws/disk_stats")
DISKS = os.getenv("DISKS", "iscsi-nvme/uzhst_march,iscsi-nvme/uzhst_jns")

# Initialize a Socket.IO client
sio = socketio.Client()


# Define event handler for connection
@sio.event
def connect():
    print("Successfully connected to the server.")
    # Emit 'my_ping' event to test the connection
    sio.emit("my_ping")


# Define event handler for 'response' event
@sio.on("response")
def handle_response(data):
    print("Received response from the server:", data)


# Define event handler for 'disk_stats_response' event
@sio.on("disk_stats_response")
def handle_disk_stats_response(data):
    print("Received disk stats response:", data)


@sio.on("pong")
def handle_pong():
    print("Received pong.")


# Define event handler for disconnection
@sio.event
def disconnect():
    print("Disconnected from the server.")


if __name__ == "__main__":
    # The disk list is passed in the query string, exactly like the frontend does.
    # After that the server pushes stats on its own, no polling required.
    sio.connect(f"{WS_URL}?{urlencode({'disks': DISKS})}", socketio_path=WS_PATH)

    # Changing the subscription without reconnecting
    time.sleep(2)
    sio.emit("subscribe", {"disks": DISKS.split(",")})

    # One-off request, for clients that prefer to poll
    sio.emit("send_stats", {"disks": DISKS})

    # Wait long enough to observe at least one pushed frame
    time.sleep(30)

    # Disconnect from the server
    sio.disconnect()
