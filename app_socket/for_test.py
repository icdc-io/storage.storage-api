import time

import socketio

# Initialize a Socket.IO client
sio = socketio.Client()


# Define event handler for connection
@sio.event
def connect():
    print("Successfully connected to the server.")
    # Emit 'my_ping' event to test the connection
    sio.emit("my_ping", namespace="/ws/disk_stats")


# Define event handler for 'response' event
@sio.on("response", namespace="/ws/disk_stats")
def handle_response(data):
    print("Received response from the server:", data)


# Define event handler for 'disk_stats_response' event
@sio.on("disk_stats_response", namespace="/ws/disk_stats")
def handle_disk_stats_response(data):
    print("Received disk stats response:", data)


# Define event handler for disconnection
@sio.event
def disconnect():
    print("Disconnected from the server.")


if __name__ == "__main__":
    # Connect to the Socket.IO server with the appropriate namespace
    sio.connect("ws://localhost:8080", namespaces=["/ws/disk_stats"])

    # Allow some time for the connection to establish
    time.sleep(1)

    # Emit a 'send_stats' event with a query parameter
    # Assuming 'disks' is a valid parameter the server is expecting
    sio.emit(
        "send_stats",
        {"disks": "iscsi-nvme/uzhst_march,iscsi-nvme/uzhst_jns"},
        namespace="/ws/disk_stats",
    )

    # Emit a 'my_ping' event to check if the server responds
    sio.emit("my_ping", namespace="/ws/disk_stats")

    # Wait for events (give some time for responses)
    # Adjust the sleep time if necessary to ensure you receive responses before disconnecting
    time.sleep(10)

    # Disconnect from the server
    sio.disconnect()
