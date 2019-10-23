"""
Define tables in Postgres database
"""
import sys
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from main import flask_app

# Base declaration for SQLAlchemy
Base = declarative_base()

# Configure Flask app for SQLAlchemy
db = SQLAlchemy(flask_app)

migrate = Migrate(flask_app, db)

# Does not run seeding in migration context
if len(sys.argv) < 2 or sys.argv[1] != 'db':
    import app.seed as seed
    # seed.seed(db.engine)
    seed.seed()