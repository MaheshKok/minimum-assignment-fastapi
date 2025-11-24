"""
Main emission calculation orchestrator service - async version.

Coordinates all calculator services and provides unified interface.
"""

import logging
from decimal import Decimal
from typing import Any, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import (
    AirTravelActivityDBModel,
    ElectricityActivityDBModel,
    EmissionResultDBModel,
    GoodsServicesActivityDBModel,
)
from app.utils.constants import ActivityType

from .electricity_calculator import ElectricityCalculator
from .goods_services_calculator import GoodsServicesCalculator
from .travel_calculator import TravelCalculator

logger = logging.getLogger(__name__)


class EmissionCalculationError(Exception):
    """
    Exception raised when emission calculation fails.

    Provides context about which activity failed and why, preserving
    the original exception if one was caught.
    """

    def __init__(
        self, activity, message: str, original_exception: Exception | None = None
    ):
        self.activity = activity
        self.activity_id = getattr(activity, "id", None)
        self.activity_type = getattr(activity, "activity_type", "Unknown")
        self.original_exception = original_exception

        # Build detailed error message with context
        error_msg = (
            f"Failed to calculate emissions for {self.activity_type} "
            f"activity {self.activity_id}: {message}"
        )

        if original_exception:
            error_msg += (
                f"\nCaused by: {type(original_exception).__name__}: {original_exception}"
            )

        super().__init__(error_msg)


# Type alias for activity instances
ActivityInstance = Union[
    ElectricityActivityDBModel,
    GoodsServicesActivityDBModel,
    AirTravelActivityDBModel,
]


class EmissionCalculationService:
    """
    Main orchestrator for emission calculations.

    Coordinates calculator services and provides batch processing capabilities.
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session."""
        self.session = session
        self.electricity_calculator = ElectricityCalculator(session)
        self.goods_services_calculator = GoodsServicesCalculator(session)
        self.travel_calculator = TravelCalculator(session)

    async def calculate_single(
        self,
        activity: ActivityInstance,
        fuzzy_threshold: int = 80,
        raise_on_error: bool = False,
    ) -> EmissionResultDBModel | None:
        """
        Calculate emissions for a single activity.

        Automatically routes to the appropriate calculator based on activity type.

        Args:
            activity: Activity instance (any type)
            fuzzy_threshold: Minimum fuzzy match threshold (0-100)
            raise_on_error: If True, raise exceptions instead of returning None

        Returns:
            EmissionResultDBModel instance if successful, None otherwise

        Raises:
            ValueError: If no calculator found for activity type
            EmissionCalculationError: If calculation fails

        Example:
            >>> service = EmissionCalculationService(session)
            >>> result = await service.calculate_single(activity)
            >>> print(f"Emissions: {result.co2e_tonnes} tonnes")
        """
        activity_type = activity.activity_type

        logger.info(f"Calculating emissions for {activity_type} activity {activity.id}")

        try:
            # Route to appropriate calculator
            if activity_type == ActivityType.ELECTRICITY:
                result = await self.electricity_calculator.calculate(
                    activity, fuzzy_threshold=fuzzy_threshold
                )
            elif activity_type == ActivityType.GOODS_SERVICES:
                result = await self.goods_services_calculator.calculate(
                    activity, fuzzy_threshold=fuzzy_threshold
                )
            elif activity_type == ActivityType.AIR_TRAVEL:
                result = await self.travel_calculator.calculate(
                    activity, fuzzy_threshold=fuzzy_threshold
                )
            else:
                error_msg = f"No calculator found for activity type: {activity_type}"
                logger.error(error_msg)
                if raise_on_error:
                    raise ValueError(error_msg)
                return None

            # If result is None and raise_on_error=True, raise informative exception
            if result is None and raise_on_error:
                raise EmissionCalculationError(
                    activity,
                    "Calculator returned None - likely no matching emission factor found",
                )

            return result

        except EmissionCalculationError:
            # Already wrapped, just re-raise
            raise

        except Exception as e:
            # Unexpected exception during calculation
            logger.error(
                f"Failed to calculate emissions for {activity_type} activity {activity.id}: {e}",
                exc_info=True,
            )
            if raise_on_error:
                raise EmissionCalculationError(
                    activity, "Unexpected error during calculation", original_exception=e
                ) from e
            return None

    async def calculate_batch(
        self,
        activities: list[ActivityInstance],
        fuzzy_threshold: int = 80,
        fail_fast: bool = False,
    ) -> dict[str, Any]:
        """
        Calculate emissions for multiple activities (batch processing).

        Args:
            activities: List of activity instances (can be mixed types)
            fuzzy_threshold: Minimum fuzzy match threshold
            fail_fast: If True, stop on first error and rollback all changes

        Returns:
            Dictionary with results, statistics, and errors

        Example:
            >>> service = EmissionCalculationService(session)
            >>> summary = await service.calculate_batch(activities)
            >>> print(f"Processed: {summary['statistics']['total_processed']}")
        """
        logger.info(f"Starting batch calculation for {len(activities)} activities")

        results = []
        errors = []
        stats_by_type = {}

        if fail_fast:
            # Use raise_on_error=True for fail-fast mode
            for activity in activities:
                result = await self.calculate_single(
                    activity, fuzzy_threshold, raise_on_error=True
                )

                # result is guaranteed not None here
                results.append(result)

                # Track statistics by activity type
                activity_type = activity.activity_type
                if activity_type not in stats_by_type:
                    stats_by_type[activity_type] = {
                        "count": 0,
                        "total_co2e": Decimal("0"),
                    }

                stats_by_type[activity_type]["count"] += 1
                stats_by_type[activity_type]["total_co2e"] += result.co2e_tonnes

            # Commit all at once if fail_fast succeeds
            await self.session.commit()
        else:
            # Process without fail-fast, collect errors
            for activity in activities:
                try:
                    result = await self.calculate_single(activity, fuzzy_threshold)

                    if result:
                        results.append(result)

                        # Track statistics by activity type
                        activity_type = activity.activity_type
                        if activity_type not in stats_by_type:
                            stats_by_type[activity_type] = {
                                "count": 0,
                                "total_co2e": Decimal("0"),
                            }

                        stats_by_type[activity_type]["count"] += 1
                        stats_by_type[activity_type]["total_co2e"] += result.co2e_tonnes
                    else:
                        errors.append(
                            {
                                "activity_id": str(activity.id),
                                "activity_type": activity.activity_type,
                                "error": "Calculation returned None",
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing activity {activity.id}: {e}",
                        exc_info=True,
                    )
                    errors.append(
                        {
                            "activity_id": str(activity.id),
                            "activity_type": activity.activity_type,
                            "error": str(e),
                        }
                    )

            # Commit after batch processing
            await self.session.commit()

        # Calculate overall statistics
        total_co2e = sum(r.co2e_tonnes for r in results)
        success_rate = (len(results) / len(activities) * 100) if activities else 0

        summary = {
            "results": results,
            "statistics": {
                "total_activities": len(activities),
                "total_processed": len(results),
                "total_errors": len(errors),
                "success_rate": f"{success_rate:.2f}%",
                "total_co2e_tonnes": float(total_co2e),
                "by_activity_type": {
                    k: {"count": v["count"], "total_co2e": float(v["total_co2e"])}
                    for k, v in stats_by_type.items()
                },
            },
            "errors": errors,
        }

        logger.info(
            f"Batch calculation complete: {len(results)}/{len(activities)} successful, "
            f"{total_co2e} tonnes CO2e total"
        )

        return summary

    async def calculate_all_pending(
        self,
        fuzzy_threshold: int = 80,
    ) -> dict[str, Any]:
        """
        Calculate emissions for all activities that don't have results yet.

        Args:
            fuzzy_threshold: Minimum fuzzy match threshold

        Returns:
            Dictionary with results and statistics

        Example:
            >>> service = EmissionCalculationService(session)
            >>> summary = await service.calculate_all_pending()
            >>> print(f"New calculations: {summary['statistics']['total_processed']}")
        """
        logger.info("Finding all activities without emission results")

        # Get IDs of activities that already have results
        existing_result_stmt = select(EmissionResultDBModel.activity_id).distinct()
        existing_result = await self.session.execute(existing_result_stmt)
        existing_ids = set(existing_result.scalars().all())

        # Get pending activities (those without results)
        pending_activities = []

        # Electricity activities
        elec_stmt = select(ElectricityActivityDBModel)
        elec_result = await self.session.execute(elec_stmt)
        for activity in elec_result.scalars().all():
            if activity.id not in existing_ids:
                pending_activities.append(activity)

        # Goods/Services activities
        goods_stmt = select(GoodsServicesActivityDBModel)
        goods_result = await self.session.execute(goods_stmt)
        for activity in goods_result.scalars().all():
            if activity.id not in existing_ids:
                pending_activities.append(activity)

        # Air Travel activities
        travel_stmt = select(AirTravelActivityDBModel)
        travel_result = await self.session.execute(travel_stmt)
        for activity in travel_result.scalars().all():
            if activity.id not in existing_ids:
                pending_activities.append(activity)

        logger.info(f"Found {len(pending_activities)} pending activities")

        if not pending_activities:
            return {
                "results": [],
                "statistics": {
                    "total_activities": 0,
                    "total_processed": 0,
                    "total_errors": 0,
                    "success_rate": "100.00%",
                    "total_co2e_tonnes": 0.0,
                    "by_activity_type": {},
                },
                "errors": [],
            }

        # Process batch
        return await self.calculate_batch(pending_activities, fuzzy_threshold=fuzzy_threshold)

    async def recalculate_activity(
        self,
        activity: ActivityInstance,
        fuzzy_threshold: int = 80,
    ) -> EmissionResultDBModel | None:
        """
        Recalculate emissions for an activity (deletes old result first).

        Useful when activity data or emission factors have been updated.

        Args:
            activity: Activity instance
            fuzzy_threshold: Minimum fuzzy match threshold

        Returns:
            New EmissionResultDBModel instance

        Example:
            >>> activity.usage_kwh = Decimal("2000.00")
            >>> service = EmissionCalculationService(session)
            >>> new_result = await service.recalculate_activity(activity)
        """
        logger.info(
            f"Recalculating emissions for {activity.activity_type} activity {activity.id}"
        )

        # Delete existing results for this activity
        delete_stmt = select(EmissionResultDBModel).where(
            EmissionResultDBModel.activity_type == activity.activity_type,
            EmissionResultDBModel.activity_id == activity.id,
        )
        delete_result = await self.session.execute(delete_stmt)
        existing_results = delete_result.scalars().all()

        for existing in existing_results:
            await self.session.delete(existing)

        if existing_results:
            logger.info(f"Deleted {len(existing_results)} existing result(s)")
            await self.session.flush()

        # Calculate new result
        return await self.calculate_single(activity, fuzzy_threshold=fuzzy_threshold)

    async def calculate_by_activity_id(
        self,
        activity_type: str,
        activity_id: UUID,
        fuzzy_threshold: int = 80,
        recalculate: bool = False,
    ) -> EmissionResultDBModel | None:
        """
        Calculate emissions for an activity by type and ID.

        Args:
            activity_type: Activity type (from ActivityType enum)
            activity_id: Activity UUID
            fuzzy_threshold: Minimum fuzzy match threshold
            recalculate: If True, delete existing result first

        Returns:
            EmissionResultDBModel instance or None

        Example:
            >>> result = await service.calculate_by_activity_id(
            ...     ActivityType.ELECTRICITY,
            ...     UUID("..."),
            ...     recalculate=True
            ... )
        """
        # Fetch activity based on type
        if activity_type == ActivityType.ELECTRICITY:
            stmt = select(ElectricityActivityDBModel).where(
                ElectricityActivityDBModel.id == activity_id
            )
        elif activity_type == ActivityType.GOODS_SERVICES:
            stmt = select(GoodsServicesActivityDBModel).where(
                GoodsServicesActivityDBModel.id == activity_id
            )
        elif activity_type == ActivityType.AIR_TRAVEL:
            stmt = select(AirTravelActivityDBModel).where(
                AirTravelActivityDBModel.id == activity_id
            )
        else:
            logger.error(f"Unknown activity type: {activity_type}")
            return None

        result = await self.session.execute(stmt)
        activity = result.scalars().first()

        if not activity:
            logger.error(f"Activity not found: {activity_type} {activity_id}")
            return None

        if recalculate:
            return await self.recalculate_activity(activity, fuzzy_threshold)
        else:
            return await self.calculate_single(activity, fuzzy_threshold)
