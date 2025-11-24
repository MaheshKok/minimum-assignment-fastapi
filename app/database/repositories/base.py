"""
Base repository with common CRUD operations.

Provides generic database operations that can be inherited by specific repositories.
"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Provides generic database access methods for any SQLAlchemy model.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, **data: Any) -> ModelType:
        """
        Create a new record.

        Args:
            **data: Field values for the new record

        Returns:
            Created model instance
        """
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        Get record by ID.

        Args:
            id: Record UUID

        Returns:
            Model instance if found, None otherwise
        """
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self, skip: int = 0, limit: int = 100, filters: Optional[Dict] = None
    ) -> List[ModelType]:
        """
        Get all records with optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional dict of field:value filters

        Returns:
            List of model instances
        """
        stmt = select(self.model)

        # Apply filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, id: UUID, **data: Any) -> Optional[ModelType]:
        """
        Update record by ID.

        Args:
            id: Record UUID
            **data: Fields to update

        Returns:
            Updated model instance if found, None otherwise
        """
        stmt = update(self.model).where(self.model.id == id).values(**data)
        await self.session.execute(stmt)
        await self.session.flush()

        # Fetch and return updated instance
        return await self.get_by_id(id)

    async def delete(self, id: UUID) -> bool:
        """
        Delete record by ID (hard delete).

        Args:
            id: Record UUID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def soft_delete(self, id: UUID) -> Optional[ModelType]:
        """
        Soft delete record by ID (sets is_deleted=True).

        Only works if model has is_deleted field.

        Args:
            id: Record UUID

        Returns:
            Updated model instance if found, None otherwise
        """
        if not hasattr(self.model, "is_deleted"):
            raise AttributeError(f"{self.model.__name__} does not support soft delete")

        return await self.update(id, is_deleted=True)

    async def count(self, filters: Optional[Dict] = None) -> int:
        """
        Count records with optional filtering.

        Args:
            filters: Optional dict of field:value filters

        Returns:
            Number of matching records
        """
        stmt = select(self.model)

        # Apply filters if provided
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def exists(self, id: UUID) -> bool:
        """
        Check if record exists by ID.

        Args:
            id: Record UUID

        Returns:
            True if exists, False otherwise
        """
        instance = await self.get_by_id(id)
        return instance is not None

    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Create multiple records in bulk.

        Args:
            items: List of dicts containing field values

        Returns:
            List of created model instances
        """
        instances = [self.model(**item) for item in items]
        self.session.add_all(instances)
        await self.session.flush()

        # Refresh all instances
        for instance in instances:
            await self.session.refresh(instance)

        return instances
