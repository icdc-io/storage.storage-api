# controllers/health_check_controller.py
import psycopg2
from flask import Response

import app.consts as consts


def health_check():
    """
    Health check logic for the Flask application.
    """
    db_status = "ok"
    try:
        # Attempt to establish a connection to the database
        conn = psycopg2.connect(
            dbname=consts.DATABASE_NAME,
            user=consts.DATABASE_USERNAME,
            password=consts.DATABASE_PASSWORD,
            host=consts.DATABASE_HOST,
            port=consts.DATABASE_PORT,
        )
        conn.close()
    except psycopg2.OperationalError:
        db_status = "error"

    # Check the overall status based on db_status
    if db_status == "ok":
        status_code = 200
        status_message = '{"status": "ok"}'
    else:
        status_code = 500
        status_message = '{"status": "error"}'

    return Response(
        response=status_message, status=status_code, mimetype="application/json"
    )
