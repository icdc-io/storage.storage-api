"""
Relation models
readme: https://flask-sqlalchemy.palletsprojects.com/en/2.x/models/#many-to-many-relationships
"""


from app.database import db

# Define tables
iscsi_assigned_clients = db.Table(
    "iscsi_assigned_clients",
    db.Column("client_id", db.Integer, db.ForeignKey("iscsi_clients.id")),
    db.Column("disk_id", db.Integer, db.ForeignKey("iscsi_disks.id")),
)
