import sys
from flask import Flask
import app.consts as consts
from app.loggers import log

# we can set level only after consts are imported
log.setLevel(consts.LOG_LEVEL)
db_conn = "postgresql://{}:{}@{}:{}/{}".format(
    consts.DATABASE_USERNAME,
    consts.DATABASE_PASSWORD,
    consts.DATABASE_HOST,
    consts.DATABASE_PORT,
    consts.DATABASE_NAME,
)

flask_app = Flask(__name__, template_folder="tmp")
flask_app.config.from_object(__name__)
flask_app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
flask_app.config["SQLALCHEMY_DATABASE_URI"] = db_conn

from app import database
from app import router
