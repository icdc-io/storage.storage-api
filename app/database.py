"""
Define tables in Postgres database
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()

# Does not run seeding in migration context
# if len(sys.argv) < 2 or sys.argv[1] != 'db':
#     import app.seed as seed
#     # seed.seed(db.engine)
#     seed.seed()
