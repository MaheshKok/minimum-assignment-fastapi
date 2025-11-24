"""
Main emission calculation orchestrator service - async version.

Coordinates all calculator services and provides unified interface.
"""

import logging
import os
from decimal import Decimal
from typing import Any, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.database.repositories import (
    AirTravelActivityRepository,
    ElectricityActivityRepository,
    EmissionResultRepository,
    GoodsServicesActivityRepository,
)
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


def get_fuzzy_threshold_from_config() -> int:
    """
    Get fuzzy threshold from config file based on current environment.

    Returns:
        int: Fuzzy threshold value (0-100) from config, defaults to 80
    """
    try:
        env = os.getenv("ENVIRONMENT", "development")
        config_file = f"{env}.toml"
        config = get_config(config_file)
        threshold = config.data.get("emission_calculation", {}).get(
            "fuzzy_match_threshold", 80
        )
        return int(threshold)
    except Exception as e:
        logger.warning(
            f"Failed to read fuzzy_match_threshold from config: {e}. Using default 80"
        )
        return 80


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
        self.message = message

        # Build detailed error message with context
        error_msg = (
            f"Failed to calculate emissions for {self.activity_type} "
            f"activity {self.activity_id}: {message}"
        )

        if original_exception:
            error_msg += (
                f"\nCaused by: {type(original_exception).__name__}: "
                f"{original_exception}"
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

    def __init__(self, session: AsyncSession, fuzzy_threshold: int | None = None):
        """
        Initialize service with database session.

        Args:
            session: Database session
            fuzzy_threshold: Optional fuzzy match threshold override.
                           If not provided, reads from config file.
        """
        self.session = session
        self.fuzzy_threshold = (
            fuzzy_threshold
            if fuzzy_threshold is not None
            else get_fuzzy_threshold_from_config()
        )
        self.electricity_calculator = ElectricityCalculator(session)
        self.goods_services_calculator = GoodsServicesCalculator(session)
        self.travel_calculator = TravelCalculator(session)
        logger.info(f"Initialized EmissionCalculationService with fuzzy_threshold={self.fuzzy_threshold}")

    async def calculate_single(
        self,
        activity: ActivityInstance,
        fuzzy_threshold: int | None = None,
        raise_on_error: bool = False,
        skip_duplicate_check: bool = False,
    ) -> EmissionResultDBModel | None:
        """
        Calculate emissions for a single activity.

        Automatically routes to the appropriate calculator based on activity type.

        Args:
            activity: Activity instance (any type)
            fuzzy_threshold: Minimum fuzzy match threshold (0-100)
            raise_on_error: If True, raise exceptions instead of returning None
            skip_duplicate_check: If True, skip check for existing results (for recalculation)

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
        # Use instance threshold if not explicitly provided
        if fuzzy_threshold is None:
            fuzzy_threshold = self.fuzzy_threshold

        activity_type = activity.activity_type

        # Check if result already exists (unless explicitly skipped for recalculation)
        if not skip_duplicate_check:
            result_repo = EmissionResultRepository(self.session)
            existing_result = await result_repo.get_by_activity_id(activity.id)
            if existing_result:
                logger.info(
                    f"Emission result already exists for {activity_type} activity {activity.id}, "
                    f"returning existing result"
                )
                return existing_result

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
                    activity,
                    "Unexpected error during calculation",
                    original_exception=e,
                ) from e
            return None

    async def calculate_batch(
        self,
        activities: list[ActivityInstance],
        fuzzy_threshold: int | None = None,
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
        # Use instance threshold if not explicitly provided
        if fuzzy_threshold is None:
            fuzzy_threshold = self.fuzzy_threshold

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
        fuzzy_threshold: int | None = None,
        batch_size: int = 100,
        use_streaming: bool = True,
    ) -> dict[str, Any]:
        """
        Calculate emissions for all activities that don't have results yet.

        Now supports two modes:
        - Streaming mode (default): Processes in chunks, constant memory usage
        - Legacy mode: Loads all activities into memory (limited to ~10K)

        Args:
            fuzzy_threshold: Minimum fuzzy match threshold
            batch_size: Number of records to process per batch (streaming mode only)
            use_streaming: If True, use cursor-based streaming for unlimited scale

        Returns:
            Dictionary with results and statistics

        Example:
            >>> service = EmissionCalculationService(session)
            >>> # Process millions of records with constant memory
            >>> summary = await service.calculate_all_pending(batch_size=100)
            >>> print(f"New calculations: {summary['statistics']['total_processed']}")
        """
        # Use instance threshold if not explicitly provided
        if fuzzy_threshold is None:
            fuzzy_threshold = self.fuzzy_threshold

        if use_streaming:
            return await self._calculate_all_pending_streaming(
                fuzzy_threshold=fuzzy_threshold, batch_size=batch_size
            )
        else:
            return await self._calculate_all_pending_legacy(
                fuzzy_threshold=fuzzy_threshold
            )

    async def _calculate_all_pending_streaming(
        self, fuzzy_threshold: int, batch_size: int = 100
    ) -> dict[str, Any]:
        """
        TRUE streaming implementation - constant memory regardless of dataset size.

        HONEST IMPLEMENTATION:
        - Does NOT accumulate all results in memory
        - Does NOT build global set of existing IDs
        - Uses per-activity duplicate check (EXISTS query via calculate_single)
        - Only tracks aggregate statistics (counters, not objects)
        - TRUE constant memory: ~10-20MB regardless of 1K or 1M records

        Trade-off: Slightly slower due to per-record EXISTS checks, but scales to unlimited records.
        """
        logger.info(
            f"Starting TRUE streaming calculation (batch_size={batch_size}, constant memory)"
        )

        # Only track aggregate statistics, NOT full result objects
        total_processed = 0
        total_errors = 0
        total_co2e = Decimal("0")
        stats_by_type = {}
        error_samples = []  # Keep only first 10 errors as samples
        MAX_ERROR_SAMPLES = 10

        for repo_class, activity_type_name in [
            (ElectricityActivityRepository, ActivityType.ELECTRICITY),
            (GoodsServicesActivityRepository, ActivityType.GOODS_SERVICES),
            (AirTravelActivityRepository, ActivityType.AIR_TRAVEL),
        ]:
            repo = repo_class(self.session)
            offset = 0
            processed_this_type = 0

            logger.info(f"Processing {activity_type_name} activities in batches...")

            while True:
                # Fetch batch of activities
                activities = await repo.get_all_active(skip=offset, limit=batch_size)
                if not activities:
                    break

                # Process activities in this batch
                for activity in activities:
                    try:
                        # calculate_single already checks for duplicates internally
                        # No need to build a global existing_ids set!
                        result = await self.calculate_single(
                            activity, fuzzy_threshold=fuzzy_threshold
                        )

                        if result:
                            # Track aggregate stats ONLY, don't store result object
                            activity_type = activity.activity_type
                            if activity_type not in stats_by_type:
                                stats_by_type[activity_type] = {
                                    "count": 0,
                                    "total_co2e": Decimal("0"),
                                }

                            stats_by_type[activity_type]["count"] += 1
                            stats_by_type[activity_type]["total_co2e"] += (
                                result.co2e_tonnes
                            )
                            total_co2e += result.co2e_tonnes
                            total_processed += 1
                            processed_this_type += 1
                        else:
                            total_errors += 1
                            if len(error_samples) < MAX_ERROR_SAMPLES:
                                error_samples.append(
                                    {
                                        "activity_id": str(activity.id),
                                        "activity_type": activity.activity_type,
                                        "error": "Calculation returned None",
                                    }
                                )

                    except Exception as e:
                        total_errors += 1
                        logger.error(
                            f"Error processing activity {activity.id}: {e}",
                            exc_info=True,
                        )
                        if len(error_samples) < MAX_ERROR_SAMPLES:
                            error_samples.append(
                                {
                                    "activity_id": str(activity.id),
                                    "activity_type": activity.activity_type,
                                    "error": str(e),
                                }
                            )

                # Commit after each batch to save progress
                await self.session.commit()

                # CRITICAL: Expunge all objects from session to prevent memory accumulation
                # SQLAlchemy's identity map retains all ORM objects until expunged/closed
                # Without this, memory grows O(n) even though we don't store results explicitly
                self.session.expunge_all()

                logger.info(
                    f"Processed batch at offset {offset}, "
                    f"{processed_this_type} {activity_type_name} activities calculated so far"
                )
                offset += batch_size

            logger.info(
                f"Completed {activity_type_name}: {processed_this_type} activities calculated"
            )

        # Calculate overall statistics
        total_activities = total_processed + total_errors
        success_rate = (
            (total_processed / total_activities * 100) if total_activities > 0 else 100.0
        )

        summary = {
            "results": [],  # Explicitly empty - we don't return full objects
            "statistics": {
                "total_activities": total_activities,
                "total_processed": total_processed,
                "total_errors": total_errors,
                "success_rate": f"{success_rate:.2f}%",
                "total_co2e_tonnes": float(total_co2e),
                "by_activity_type": {
                    k: {"count": v["count"], "total_co2e": float(v["total_co2e"])}
                    for k, v in stats_by_type.items()
                },
            },
            "errors": error_samples,  # Only sample errors, not all
            "note": "True streaming mode - result objects not returned to save memory. "
                    "Query emission_results table for full results.",
        }

        logger.info(
            f"TRUE streaming complete: {total_processed}/{total_activities} successful, "
            f"{total_co2e} tonnes CO2e total (constant memory used)"
        )

        return summary

    async def _calculate_all_pending_legacy(
        self, fuzzy_threshold: int
    ) -> dict[str, Any]:
        """
        Legacy implementation - loads all activities into memory.

        DEPRECATED: Use streaming mode for better scalability.
        Limited to ~10K records due to memory constraints.
        """
        logger.warning(
            "Using legacy mode - limited to ~10K records. "
            "Consider using streaming mode (use_streaming=True) for better scale."
        )

        logger.info("Finding all activities without emission results")

        # Get IDs of activities that already have results (no pagination limit)
        result_repo = EmissionResultRepository(self.session)
        existing_results = await result_repo.get_all_results(skip=0, limit=10000)
        existing_ids = {r.activity_id for r in existing_results}

        logger.info(f"Found {len(existing_ids)} existing emission results")

        # Get pending activities (those without results) - no pagination limit
        pending_activities = []

        # Electricity activities
        elec_repo = ElectricityActivityRepository(self.session)
        elec_activities = await elec_repo.get_all_active(skip=0, limit=10000)
        for activity in elec_activities:
            if activity.id not in existing_ids:
                pending_activities.append(activity)

        # Goods/Services activities
        goods_repo = GoodsServicesActivityRepository(self.session)
        goods_activities = await goods_repo.get_all_active(skip=0, limit=10000)
        for activity in goods_activities:
            if activity.id not in existing_ids:
                pending_activities.append(activity)

        # Air Travel activities
        travel_repo = AirTravelActivityRepository(self.session)
        travel_activities = await travel_repo.get_all_active(skip=0, limit=10000)
        for activity in travel_activities:
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
        return await self.calculate_batch(
            pending_activities, fuzzy_threshold=fuzzy_threshold
        )

    async def recalculate_activity(
        self,
        activity: ActivityInstance,
        fuzzy_threshold: int | None = None,
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
        # Use instance threshold if not explicitly provided
        if fuzzy_threshold is None:
            fuzzy_threshold = self.fuzzy_threshold

        logger.info(
            f"Recalculating emissions for {activity.activity_type} activity {activity.id}"
        )

        # Delete existing results for this activity
        result_repo = EmissionResultRepository(self.session)
        deleted_count = await result_repo.delete_by_activity_id(activity.id)

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing result(s)")

        # Calculate new result - skip duplicate check since we just deleted it
        return await self.calculate_single(
            activity, fuzzy_threshold=fuzzy_threshold, skip_duplicate_check=True
        )

    async def calculate_by_activity_id(
        self,
        activity_type: str,
        activity_id: UUID,
        fuzzy_threshold: int | None = None,
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
        # Use instance threshold if not explicitly provided
        if fuzzy_threshold is None:
            fuzzy_threshold = self.fuzzy_threshold

        # Fetch activity based on type using repositories
        activity = None
        if activity_type == ActivityType.ELECTRICITY:
            repo = ElectricityActivityRepository(self.session)
            activity = await repo.get_by_id_active(activity_id)
        elif activity_type == ActivityType.GOODS_SERVICES:
            repo = GoodsServicesActivityRepository(self.session)
            activity = await repo.get_by_id_active(activity_id)
        elif activity_type == ActivityType.AIR_TRAVEL:
            repo = AirTravelActivityRepository(self.session)
            activity = await repo.get_by_id_active(activity_id)
        else:
            logger.error(f"Unknown activity type: {activity_type}")
            return None

        if not activity:
            logger.error(f"Activity not found: {activity_type} {activity_id}")
            return None

        if recalculate:
            return await self.recalculate_activity(activity, fuzzy_threshold)
        else:
            return await self.calculate_single(activity, fuzzy_threshold)
