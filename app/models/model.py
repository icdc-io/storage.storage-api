"""
Abstract model
"""

import marshmallow
from sqlalchemy import select

from app.database import db
from app.loggers import log


class AbstractModel(db.Model):
    """
    Abstract base class providing common database operations
    and filtering utilities for all models.
    """
    __abstract__ = True
    RESOURCE_NAME: str  # e.g., "iscsi.disks" or "s3.buckets"

    # ----------------------------
    # Instance methods
    # ----------------------------

    def _commit(self):
        """
        Commit the current object to the database.
        """
        try:
            db.session.add(self)
            db.session.commit()
            return self
        except Exception as e:
            log.debug(e)
            db.session.rollback()
            return None

    def save(self) -> None:
        """
        Save (insert or update) the current object in the database.
        """
        self._commit()

    def destroy(self) -> None:
        """
        Permanently delete the current object from the database.
        """
        log.debug(f"Deleting object: {self}")
        db.session.delete(self)
        db.session.commit()
        log.debug("Object deleted successfully")

    # ----------------------------
    # Class-level utility methods
    # ----------------------------

    @classmethod
    def get_by(cls, filter_param: str, value) -> db.Model | None:
        """
        Retrieve the first record matching the given column filter.
        Parameters
        ----------
        filter_param : str
            The column name to filter by.
        value : Any
            The value to match.
        Returns
        -------
        object | None
            The first matching record or None if not found.
        """
        log.debug(f"Filtering by {filter_param} = {value}")
        # NOTE: eval is used in a controlled internal environment
        result = cls.query.filter(eval(f"cls.{filter_param}") == value).first()
        log.debug(f"Result: {result}")
        return result

    @classmethod
    def schema(cls) -> marshmallow.Schema:
        """
        Return the Marshmallow schema for the model.

        This method must be implemented in each subclass to define
        its validation and serialization schema.

        Raises
        ------
        NotImplementedError
            If the method is not overridden in a subclass.
        """
        raise NotImplementedError(f"{cls.__name__}.schema() must be implemented")

    @classmethod
    def filter_object_name(cls) -> str:
        """
        Extract the logical name part from RESOURCE_NAME.

        Returns
        -------
        str
            The object part of the resource name.

        Example
        -------
        "iscsi.disks" -> "disks"
        "s3" -> "s3"
        """
        parts = cls.RESOURCE_NAME.split(".")
        return parts[1] if len(parts) == 2 else parts[0]

    @classmethod
    def related_objects(cls) -> list[tuple[type, object]]:
        """
        Return related model classes and their linking fields.

        Returns
        -------
        list[tuple[type, object]]
            List of tuples in the format:
            [
                (RelatedModelClass, cls.foreign_key_field)
            ]

        Description
        -----------
        This allows the model to recursively apply filters
        to related models, e.g., a Disk filtered by its Target.
        """
        return []

    # ----------------------------
    # Filtering and query helpers
    # ----------------------------

    @classmethod
    def apply_filters(cls, subject, request_filters: dict) -> dict:
        """
        Combine and validate filters from different sources.

        Parameters
        ----------
        subject :
            Used internally for RBAC filters.
        request_filters : dict
            Dictionary containing filters for the current model ("base")
            and for related objects.

        Returns
        -------
        dict
            Validated and merged filters for the current model.

        Notes
        -----
        Example structure of request_filters:
        {
            "disks": {"size_gb": 100},
            "base": {"name": "disk-001"},
        }

        Example of returned filters:
        {
            "size_gb": 100,
            "name": "disk-001"
        }
        """
        filters: dict = {}

        # Model-specific filters (e.g. {"disks": {...}})
        key = cls.filter_object_name()
        filters.update(request_filters.pop(key, {}))

        # Filters for the current (base) resource
        filters.update(request_filters.pop("base", {}))

        # Add RBAC or account-level filters if subject provides them
        filters.update(subject.filters(cls.RESOURCE_NAME))

        # Validate filters using Marshmallow schema
        cls.schema().load(filters, partial=True)

        return filters

    @classmethod
    def filtered(cls, subject, request_filters: dict | None = None):
        """
        Build a SQLAlchemy query for the model, applying all filters
        and recursively filtering related objects.

        Parameters
        ----------
        subject :
            Used internally for access-based filters.
        request_filters : dict | None, optional
            Dictionary of filters from the request payload.

        Returns
        -------
        sqlalchemy.orm.Query
            SQLAlchemy query object with applied filters.

        Notes
        -----
        related_objects define dependencies, for example:
            [
                (IscsiTargets, cls.target_id)
            ]

        In that case, it performs subqueries on related tables and
        filters results accordingly.
        """
        if request_filters is None:
            request_filters = {}

        # Apply all filters and validate them
        filters = cls.apply_filters(subject, request_filters)

        query = cls.query
        # Recursively apply filters to related models
        for related_model, field in cls.related_objects():
            related_subquery = (
                related_model.filtered(subject, request_filters)
                .with_entities(related_model.id)
                .subquery()
            )
            query = query.filter(field.in_(select(related_subquery.c.id)))

        # Apply final filters to the main query
        return query.filter_by(**filters)
