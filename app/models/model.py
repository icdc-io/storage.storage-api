"""
Abstract model
"""
from app.loggers import log
from app.database import db


class AbstractModel:
    def _commit(self, db):
        """
        Commit the current object to the database.

        :param db: the database session
        :type db: object
        :return: the committed object or None if an exception occurs
        :rtype: object or None
        """
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except Exception as e:
            log.debug(e)
            db.session.rollback()
            return None

    def _delete(self, db):
        """
        Deletes the current object from the database using the provided db session.

        :param db: The session object for the database.
        :return: None
        """
        log.debug(f"Deleting object: {self}")
        db.session.delete(self)
        db.session.commit()
        log.debug("Object deleted successfully")

    # UZH: idk why _delete is a protected method and why it needs db argument
    # when db is already imported here, now I prefere the realiaztion below
    def destroy(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def _delete_by(cls, attribute, value):
        """
        Delete entries by a specific attribute and its value.
        :param attribute: The attribute based on which the deletion is to be performed.
        :param value: The value of the attribute.
        :return: Tuple of (bool, str) indicating success status and message
        """

        # Find the objects to delete. This uses `filter_by` to dynamically filter based on attribute and value
        objects_to_delete = cls.query.filter_by(**{attribute: value}).all()

        if not objects_to_delete:
            return False, "No entries found with the given attribute and value."

        # Delete each object
        for obj in objects_to_delete:
            db.session.delete(obj)

        # Commit the changes to the database
        db.session.commit()
        return True, f"Entries successfully deleted. {objects_to_delete}"

    def _serialize(self):
        return "Method serialize() is not implemented in this class"

    @classmethod
    def get_by(cls, filter_param, value):
        """
        WHERE SQL STATEMENT
        """
        log.debug(f"Filtering by {filter_param} = {value}")
        result = cls.query.filter(eval(f"cls.{filter_param}") == value).first()
        log.debug(f"Result: {result}")
        return result

    @classmethod
    def filtered(cls, subject):
        return cls.query.filter_by(**subject.filters)

    def response_filter(self, fields, hide):
        """
        Hide attributes. Needed for resolve recursion issue
        """
        """
        Hide attributes. Needed for resolve recursion issue
        """
        response = {}
        if not hide:
            for key in fields:
                response[key] = eval(fields.get(key))
            return response
        for key in fields:
            if key not in hide:
                response[key] = eval(fields.get(key))
        return response
