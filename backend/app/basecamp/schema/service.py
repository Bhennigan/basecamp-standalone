"""Schema management service for Base Camp OS."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select

from app.basecamp.enums import SchemaStatus
from app.basecamp.schema.inference import (
    calculate_schema_confidence,
    inferred_schema_to_schema_fields,
)
from app.basecamp.schemas import (
    BaseCampSchemaCreate,
    BaseCampSchemaRead,
    BaseCampSchemaReadMinimal,
    BaseCampSchemaUpdate,
    SchemaFieldCreate,
    SchemaFieldRead,
    SchemaInferRequest,
    SchemaInferResponse,
)
from app.basecamp.types import InferredSchema
from app.db.models import BaseCampSchema
from app.exceptions import TracecatNotFoundError
from app.service import BaseWorkspaceService


class SchemaService(BaseWorkspaceService):
    """Service for managing Base Camp schemas."""

    service_name = "basecamp_schema"

    async def list_schemas(
        self,
        *,
        status: SchemaStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BaseCampSchemaReadMinimal]:
        """List all schemas for the workspace.

        Args:
            status: Optional filter by schema status.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of schema summaries.
        """
        conditions = [BaseCampSchema.workspace_id == self.workspace_id]

        if status:
            conditions.append(BaseCampSchema.status == status)

        stmt = (
            select(BaseCampSchema)
            .where(and_(*conditions))
            .order_by(BaseCampSchema.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        schemas = result.scalars().all()

        return [
            BaseCampSchemaReadMinimal(
                id=s.id,
                name=s.name,
                version=s.version,
                status=s.status,
            )
            for s in schemas
        ]

    async def get_schema(
        self,
        schema_id: uuid.UUID,
        *,
        version: int | None = None,
    ) -> BaseCampSchemaRead:
        """Get a schema by ID.

        Args:
            schema_id: The schema ID.
            version: Optional specific version (defaults to latest).

        Returns:
            The schema details.

        Raises:
            TracecatNotFoundError: If schema not found.
        """
        conditions = [
            BaseCampSchema.workspace_id == self.workspace_id,
            BaseCampSchema.id == schema_id,
        ]

        if version:
            conditions.append(BaseCampSchema.version == version)

        stmt = (
            select(BaseCampSchema)
            .where(and_(*conditions))
            .order_by(BaseCampSchema.version.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        schema = result.scalar_one_or_none()

        if not schema:
            raise TracecatNotFoundError(f"Schema {schema_id} not found")

        return self._schema_to_read(schema)

    async def get_schema_by_name(
        self,
        name: str,
        *,
        version: int | None = None,
    ) -> BaseCampSchemaRead:
        """Get a schema by name.

        Args:
            name: The schema name.
            version: Optional specific version (defaults to latest).

        Returns:
            The schema details.

        Raises:
            TracecatNotFoundError: If schema not found.
        """
        conditions = [
            BaseCampSchema.workspace_id == self.workspace_id,
            BaseCampSchema.name == name,
        ]

        if version:
            conditions.append(BaseCampSchema.version == version)

        stmt = (
            select(BaseCampSchema)
            .where(and_(*conditions))
            .order_by(BaseCampSchema.version.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        schema = result.scalar_one_or_none()

        if not schema:
            raise TracecatNotFoundError(f"Schema '{name}' not found")

        return self._schema_to_read(schema)

    async def create_schema(
        self,
        params: BaseCampSchemaCreate,
    ) -> BaseCampSchemaRead:
        """Create a new schema.

        Args:
            params: The schema creation parameters.

        Returns:
            The created schema.
        """
        # Check for existing schema with same name
        existing = await self._get_latest_version_for_name(params.name)
        version = existing.version + 1 if existing else 1

        # Convert field definitions
        fields_data = [
            {
                "name": f.name,
                "field_type": f.field_type,
                "nullable": f.nullable,
                "default": f.default,
                "description": f.description,
            }
            for f in params.fields
        ]

        schema = BaseCampSchema(
            workspace_id=self.workspace_id,
            name=params.name,
            description=params.description,
            version=version,
            status=SchemaStatus.DRAFT,
            fields=fields_data,
        )

        self.session.add(schema)
        await self.session.flush()
        await self.session.refresh(schema)

        self.logger.info(
            "Created schema",
            schema_id=str(schema.id),
            name=schema.name,
            version=schema.version,
        )

        return self._schema_to_read(schema)

    async def update_schema(
        self,
        schema_id: uuid.UUID,
        params: BaseCampSchemaUpdate,
    ) -> BaseCampSchemaRead:
        """Update a schema.

        Creates a new version if fields are changed.

        Args:
            schema_id: The schema ID.
            params: The update parameters.

        Returns:
            The updated schema.

        Raises:
            TracecatNotFoundError: If schema not found.
        """
        schema = await self._get_schema_model(schema_id)

        # Check if this is a field update (requires new version)
        if params.fields is not None:
            return await self._create_new_version(schema, params)

        # Simple update without version change
        if params.name is not None:
            schema.name = params.name
        if params.description is not None:
            schema.description = params.description
        if params.status is not None:
            schema.status = params.status

        await self.session.flush()
        await self.session.refresh(schema)

        self.logger.info(
            "Updated schema",
            schema_id=str(schema.id),
            version=schema.version,
        )

        return self._schema_to_read(schema)

    async def delete_schema(self, schema_id: uuid.UUID) -> None:
        """Delete a schema.

        Args:
            schema_id: The schema ID.

        Raises:
            TracecatNotFoundError: If schema not found.
        """
        schema = await self._get_schema_model(schema_id)

        await self.session.delete(schema)
        await self.session.flush()

        self.logger.info("Deleted schema", schema_id=str(schema_id))

    async def infer_schema_preview(
        self,
        request: SchemaInferRequest,
    ) -> SchemaInferResponse:
        """Preview schema inference from sample data.

        Args:
            request: The inference request with sample data.

        Returns:
            The inferred schema preview.
        """
        from app.basecamp.ingestion.parsers.json_parser import JSONParser

        # Use JSON parser for dict data
        parser = JSONParser()

        # Build field values from sample data
        all_fields: set[str] = set()
        for record in request.sample_data:
            all_fields.update(record.keys())

        field_values: dict[str, list] = {field: [] for field in all_fields}
        for record in request.sample_data:
            for field in all_fields:
                field_values[field].append(record.get(field))

        # Create inferred fields
        inferred_fields = [
            parser._create_inferred_field(name, values)
            for name, values in sorted(field_values.items())
        ]

        from app.basecamp.enums import FileFormat

        inferred_schema = InferredSchema(
            fields=inferred_fields,
            record_count=len(request.sample_data),
            source_format=request.source_format or FileFormat.JSON,
        )

        schema_fields = inferred_schema_to_schema_fields(inferred_schema)
        confidence = calculate_schema_confidence(inferred_schema)

        return SchemaInferResponse(
            inferred_fields=schema_fields,
            record_count=len(request.sample_data),
            confidence=confidence,
        )

    async def create_schema_from_inferred(
        self,
        name: str,
        inferred_schema: InferredSchema,
        *,
        description: str | None = None,
    ) -> BaseCampSchemaRead:
        """Create a schema from an inferred schema.

        Args:
            name: The schema name.
            inferred_schema: The inferred schema from parsing.
            description: Optional description.

        Returns:
            The created schema.
        """
        fields = [
            SchemaFieldCreate(
                name=f.name,
                field_type=f.inferred_type,
                nullable=f.nullable,
                default=None,
                description=None,
            )
            for f in inferred_schema.fields
        ]

        params = BaseCampSchemaCreate(
            name=name,
            description=description,
            fields=fields,
        )

        return await self.create_schema(params)

    async def _get_schema_model(self, schema_id: uuid.UUID) -> BaseCampSchema:
        """Get the raw schema model.

        Args:
            schema_id: The schema ID.

        Returns:
            The schema model.

        Raises:
            TracecatNotFoundError: If not found.
        """
        stmt = select(BaseCampSchema).where(
            and_(
                BaseCampSchema.workspace_id == self.workspace_id,
                BaseCampSchema.id == schema_id,
            )
        )

        result = await self.session.execute(stmt)
        schema = result.scalar_one_or_none()

        if not schema:
            raise TracecatNotFoundError(f"Schema {schema_id} not found")

        return schema

    async def _get_latest_version_for_name(self, name: str) -> BaseCampSchema | None:
        """Get the latest version of a schema by name.

        Args:
            name: The schema name.

        Returns:
            The latest version or None.
        """
        stmt = (
            select(BaseCampSchema)
            .where(
                and_(
                    BaseCampSchema.workspace_id == self.workspace_id,
                    BaseCampSchema.name == name,
                )
            )
            .order_by(BaseCampSchema.version.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _create_new_version(
        self,
        current: BaseCampSchema,
        params: BaseCampSchemaUpdate,
    ) -> BaseCampSchemaRead:
        """Create a new version of a schema.

        Args:
            current: The current schema.
            params: The update parameters.

        Returns:
            The new schema version.
        """
        # Convert field definitions
        fields_data = []
        if params.fields:
            fields_data = [
                {
                    "name": f.name,
                    "field_type": f.field_type,
                    "nullable": f.nullable,
                    "default": f.default,
                    "description": f.description,
                }
                for f in params.fields
            ]

        new_schema = BaseCampSchema(
            workspace_id=self.workspace_id,
            name=params.name or current.name,
            description=params.description or current.description,
            version=current.version + 1,
            status=params.status or SchemaStatus.DRAFT,
            fields=fields_data if fields_data else current.fields,
        )

        # Deprecate old version
        current.status = SchemaStatus.DEPRECATED

        self.session.add(new_schema)
        await self.session.flush()
        await self.session.refresh(new_schema)

        self.logger.info(
            "Created new schema version",
            schema_id=str(new_schema.id),
            name=new_schema.name,
            version=new_schema.version,
        )

        return self._schema_to_read(new_schema)

    def _schema_to_read(self, schema: BaseCampSchema) -> BaseCampSchemaRead:
        """Convert schema model to read schema.

        Args:
            schema: The schema model.

        Returns:
            The read schema.
        """
        fields = [
            SchemaFieldRead(
                name=f.get("name", ""),
                field_type=f.get("field_type", "str"),
                nullable=f.get("nullable", True),
                default=f.get("default"),
                description=f.get("description"),
            )
            for f in (schema.fields or [])
        ]

        return BaseCampSchemaRead(
            id=schema.id,
            name=schema.name,
            description=schema.description,
            version=schema.version,
            status=schema.status,
            fields=fields,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
        )
