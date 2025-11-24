"""
Base factory for async SQLAlchemy models following kkb_fastapi pattern.
"""
import asyncio
import inspect
from typing import Any

import factory
from factory.alchemy import SQLAlchemyOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncSQLAlchemyFactory(factory.Factory):
    """
    Base factory for creating async SQLAlchemy model instances.

    Provides async-first design with proper session management,
    SubFactory support, and get_or_create functionality.
    """

    _options_class = SQLAlchemyOptions

    class Meta:
        abstract = True

    @classmethod
    async def create(cls, **kwargs) -> Any:
        """
        Create and commit an instance asynchronously.

        Args:
            **kwargs: Attributes to set on the instance

        Returns:
            Created model instance
        """
        async with cls._meta.sqlalchemy_session() as session:
            instance = await super().create(**kwargs)
            await session.commit()
            return instance

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Create instance and return as Task/coroutine.

        This allows factories to be awaited multiple times.
        """
        async def maker_coroutine():
            for key, value in kwargs.items():
                # When using SubFactory, you'll have a Task in the corresponding kwarg
                # Await tasks to pass model instances instead
                if inspect.isawaitable(value):
                    kwargs[key] = await value

            if cls._meta.sqlalchemy_get_or_create:
                return await cls._get_or_create(model_class, *args, **kwargs)
            return await cls._save(model_class, *args, **kwargs)

        # A Task can be awaited multiple times, unlike a coroutine
        return asyncio.create_task(maker_coroutine())

    @classmethod
    async def _get_or_create(
        cls, model_class, session: AsyncSession, lookup_fields: dict
    ) -> Any:
        """
        Get existing instance or create new one.

        Args:
            model_class: SQLAlchemy model class
            session: Async database session
            lookup_fields: Fields to use for lookup

        Returns:
            Existing or newly created instance
        """
        # Build query from lookup fields
        stmt = select(model_class)
        for key, value in lookup_fields.items():
            stmt = stmt.where(getattr(model_class, key) == value)

        result = await session.execute(stmt)
        instance = result.scalars().first()

        if instance:
            return instance

        # Create new instance
        return await cls.create(**lookup_fields)

    @classmethod
    async def _save(cls, model_class, *args, **kwargs) -> Any:
        """
        Create, add instance to session and commit.

        Args:
            model_class: SQLAlchemy model class
            **kwargs: Model attributes

        Returns:
            Saved instance
        """
        async with cls._meta.sqlalchemy_session() as session:
            obj = model_class(*args, **kwargs)
            session.add(obj)
            await session.commit()
            return obj

    @classmethod
    async def create_batch(cls, size: int, **kwargs) -> list[Any]:
        """
        Create multiple instances asynchronously.

        Args:
            size: Number of instances to create
            **kwargs: Attributes to set on all instances

        Returns:
            List of created instances
        """
        return [await cls.create(**kwargs) for _ in range(size)]
