# https://docs.gunicorn.org/en/stable/configure.html
# Config for the WebSocket service (app_socket_server:app), NOT for the REST API.
bind = "0.0.0.0:8080"
access_logfile = "-"
error_logfile = "-"
loglevel = "debug"

# The default sync worker cannot serve WebSocket connections.
worker_class = "eventlet"

# Flask-SocketIO keeps client state in process memory, so more than one worker
# requires a message queue (Redis) to share it.
workers = 1

# eventlet monkey-patches the stdlib in the worker, which does not survive a
# pre-forked master.
preload_app = False

# No max_requests: recycling the worker would drop every live WebSocket connection.
timeout = 180
graceful_timeout = 120
