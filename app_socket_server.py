# app_socket_server.py

from flask import Flask
from flask_socketio import SocketIO

from app_socket.config import WS_PATH
from app_socket.namespaces import SendStatNamespace

# Initialize Flask app
app = Flask(__name__)

# Initialize Flask-SocketIO.
# `path` is the engine.io endpoint and must match the nginx location proxying to
# this service, because nginx forwards $request_uri unchanged.
socketio = SocketIO(
    app,
    async_mode=None,
    cors_allowed_origins="*",
    engineio_logger=False,
    path=WS_PATH,
)

# Register the namespace. Clients connect to the default namespace; the routing to
# this service is done by `path`, not by a socket.io namespace.
socketio.on_namespace(SendStatNamespace("/"))

# Run the application
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080)
