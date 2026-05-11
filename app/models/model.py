"""
Abstract model
"""

import marshmallow
from marshmallow import ValidationError, INCLUDE
from sqlalchemy.orm import aliased
from sqlalchemy.orm import query as sql_query

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
    def _get_related_filters(cls) -> dict:
        """
        Defines available relation filters for this model.

        Structure:
            {
                'filter_alias': (join_path, target_model),
                'filter_alias': (join_path, target_model, shortcut_alias),
            }

        Fields:
            filter_alias  (str) — the name used in request filter, e.g. filter[cluster.name]
                                  or filter[account_id] for shortcut filters
            join_path     (str) — dot-separated path of relationships to traverse,
                                  e.g. 'disk.target.cluster' means
                                  cls -> disk -> target -> cluster
            target_model  (Model) — the final model at the end of join_path,
                                    filters will be applied against its columns
            shortcut_alias (str, optional) — if provided, this filter_alias is treated
                                             as a direct field shortcut on target_model,
                                             meaning filter[account_id] maps to
                                             target_model.account_id without needing
                                             a dot notation in the request

        Examples:
            'cluster': ('disk.target.cluster', IscsiClusters)
                → filter[cluster.name]=foo
                → JOIN ... iscsi_clusters WHERE iscsi_clusters.name = 'foo'

            'account_id': ('disk.target.cluster', IscsiClusters, 'cluster')
                → filter[account_id]=2
                → shortcut: moved from base into 'cluster' group
                → JOIN ... iscsi_clusters WHERE iscsi_clusters.account_id = 2
        """
        return {}

    @classmethod
    def _preprocess_filters(cls, filters: dict) -> dict:
        """
        Moves shortcut fields from 'base' into their target relation group.

        Example:
            IN:  {'base': {'account_id': 2}, 'cluster': {'name': 'foo'}}
            OUT: {'base': {}, 'cluster': {'name': 'foo', 'account_id': 2}}

        This allows filter[account_id]=2 to be applied against IscsiClusters
        instead of being treated as a direct column on cls.
        """
        related_filters = cls._get_related_filters()
        base = filters.get("base", {})
        for field_name, value in list(base.items()):
            filter_def = related_filters.get(field_name)
            # Only process shortcut fields (those with a third element — target_relation)
            if not filter_def or len(filter_def) < 3:
                continue
            _, _, target_relation = filter_def
            filters.setdefault(target_relation, {})[field_name] = value
            del base[field_name]

        return filters

    @classmethod
    def filtered(cls, subject, request_filters=None) -> sql_query:
        """
        Applies request filters and subject scope filters to cls.query.

        Handles two types of filters:
            - base: direct column filters on this model, e.g. filter[name]=foo
            - relation: filters on related models via joins, e.g. filter[cluster.name]=foo
        """
        if request_filters is None:
            request_filters = {}

        # Merge subject scope filters (e.g. account_id restriction) into base
        request_filters.setdefault("base", {}).update(subject.filters(cls.RESOURCE_NAME))
        filters = cls._preprocess_filters(request_filters)

        query = cls.query
        # Tracks already joined nodes to avoid duplicate joins across filter iterations
        _aliases = {}
        related_filters = cls._get_related_filters()

        for relation_alias, attr_filters in filters.items():
            if relation_alias == "base":
                attr_filters = cls.schema().load(attr_filters, unknown=INCLUDE, partial=True)
                for field_name, value in attr_filters.items():
                    if not hasattr(cls, field_name):
                        raise ValidationError(f"No field {field_name} on the object")
                    query = query.filter(getattr(cls, field_name) == value)
            else:
                if relation_alias not in related_filters:
                    raise ValidationError(f"Unknown relation filter: {relation_alias}")

                join_path, related_model, *_ = related_filters[relation_alias]

                query = cls._apply_relation_join(query, join_path, relation_alias, _aliases)

                # final_alias is the aliased version of related_model at the end of join_path
                # we must filter against the alias, not the original model,
                # otherwise SQL will reference the unaliased table and break
                final_alias = _aliases[relation_alias]
                attr_filters = related_model.schema().load(attr_filters, unknown=INCLUDE, partial=True)
                for attr, value in attr_filters.items():
                    if not hasattr(related_model, attr):
                        raise ValidationError(f"No field {attr} on {relation_alias}")
                    query = query.filter(getattr(final_alias, attr) == value)

        return query.reset_joinpoint()

    @classmethod
    def _apply_relation_join(cls, query, join_path: str, relation_alias: str, _aliases: dict) -> sql_query:
        """
        Traverses join_path and adds JOIN clauses to query, skipping already joined nodes.

        Each node in the path gets an aliased version of its model to avoid
        duplicate table errors when the same table is joined via different paths.

        Alias naming:
            - Intermediate nodes: 'tablename_relation_relation' e.g. 'snapshots_disk_target'
            - Final node: relation_alias e.g. 'cluster', 'real_cluster'

        After the loop, _aliases[relation_alias] points to the final aliased model
        so filtered() can apply .filter() against it directly.
        """
        parts = join_path.split('.')
        current_model = cls
        current_path = cls.__tablename__
        for i, part in enumerate(parts):
            relation = getattr(current_model, part)
            next_model = relation.property.mapper.class_
            next_path = f"{current_path}.{part}"
            is_last = i == len(parts) - 1

            if next_path not in _aliases:
                # Intermediate nodes get a path-based name, final node gets relation_alias
                # so that _aliases[relation_alias] works as a shortcut in filtered()
                alias_name = relation_alias if is_last else next_path.replace('.', '_')
                alias = aliased(next_model, name=alias_name)
                # Pass both alias and relation so SQLAlchemy knows which FK to use
                query = query.join(alias, relation)
                _aliases[next_path] = alias

            # Always move forward from the alias, not the original model —
            # next getattr() must resolve relationships from the aliased instance
            current_model = _aliases[next_path]
            current_path = next_path

        # Shortcut so filtered() can do _aliases[relation_alias] instead of
        # reconstructing the full path key
        _aliases[relation_alias] = _aliases[f"{cls.__tablename__}.{'.'.join(parts)}"]

        return query
