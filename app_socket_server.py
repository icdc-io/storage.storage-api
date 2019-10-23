# app_socket_server.py

from flask import Flask
from flask_socketio import SocketIO

from app_socket.namespaces import SendStatNamespace

# Initialize Flask app
app = Flask(__name__)

# Initialize Flask-SocketIO
socketio = SocketIO(
    app, async_mode=None, cors_allowed_origins="*", engineio_logger=False
)

# Register the namespace
socketio.on_namespace(SendStatNamespace("/ws/disk_stats"))

# Run the application
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080)
