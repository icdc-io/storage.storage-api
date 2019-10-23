# https://docs.gunicorn.org/en/stable/configure.html
bind = "0.0.0.0:8080"
access_logfile = "-"
error_logfile = "-"
loglevel = "debug"
timeout = 180
graceful_timeout = 120
workers = 1
preload_app = True
max_requests = 1000