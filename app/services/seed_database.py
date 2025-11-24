"""
Database seeding service for loading test data from CSV files.

Usage:
    from app.services.seed_database import DatabaseSeeder

    async with DatabaseSeeder() as seeder:
        await seeder.seed_all(clear_existing=True)
"""

import csv
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories import (
    AirTravelActivityRepository,
    ElectricityActivityRepository,
    EmissionFactorRepository,
    GoodsServicesActivityRepository,
)
from app.database.schemas import (
    AirTravelActivityDBModel,
    ElectricityActivityDBModel,
    EmissionFactorDBModel,
    GoodsServicesActivityDBModel,
)
from app.database.session_manager.db_session import Database
from app.services.calculators.emission_calculator import EmissionCalculationService
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType

logger = logging.getLogger(__name__)


class DatabaseSeeder:
    """Service for seeding database with test data from CSV files."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        data_dir: str | Path = "app/test/test_data",
    ):
        """
        Initialize the database seeder.

        Args:
            session: Optional async database session. If not provided, will create one.
            data_dir: Directory containing CSV files (default: app/test/test_data)
        """
        self._session = session
        self._external_session = session is not None
        self.data_dir = Path(data_dir)

        if not self.data_dir.exists():
            raise ValueError(f"Data directory not found: {self.data_dir}")

    async def __aenter__(self):
        """Context manager entry."""
        if not self._external_session:
            db = Database()
            self._session = await db.__aenter__()
            self._db_context = db
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if not self._external_session and hasattr(self, "_db_context"):
            await self._db_context.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def session(self) -> AsyncSession:
        """Get the database session."""
        if not self._session:
            raise RuntimeError("Session not initialized. Use as context manager.")
        return self._session

    async def seed_all(
        self,
        clear_existing: bool = False,
        skip_calculations: bool = False,
    ) -> dict[str, Any]:
        """
        Seed all data from CSV files.

        Args:
            clear_existing: If True, clear existing data before seeding
            skip_calculations: If True, skip automatic emission calculations

        Returns:
            Dictionary with seeding statistics
        """
        logger.info("Starting database seeding")

        stats = {
            "emission_factors": 0,
            "electricity_activities": 0,
            "air_travel_activities": 0,
            "goods_services_activities": 0,
            "emission_results": 0,
            "errors": [],
        }

        try:
            if clear_existing:
                await self._clear_existing_data()

            # Seed data in order (emission factors first, then activities)
            stats["emission_factors"] = await self.seed_emission_factors()
            stats["electricity_activities"] = await self.seed_electricity_activities()
            stats["air_travel_activities"] = await self.seed_air_travel_activities()
            stats[
                "goods_services_activities"
            ] = await self.seed_goods_services_activities()

            await self.session.commit()

            if not skip_calculations:
                logger.info("Calculating emissions for all activities")
                calc_results = await self._calculate_all_emissions()
                stats["emission_results"] = calc_results["calculated"]
                stats["errors"].extend(calc_results.get("errors", []))

            logger.info(f"Database seeding completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error during database seeding: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def _clear_existing_data(self):
        """Clear all existing emission data."""
        logger.info("Clearing existing data")

        # Use text() for raw SQL statements (respecting relationships order)
        await self.session.execute(text("DELETE FROM emission_results"))
        await self.session.execute(text("DELETE FROM electricity_activities"))
        await self.session.execute(text("DELETE FROM air_travel_activities"))
        await self.session.execute(text("DELETE FROM goods_services_activities"))
        await self.session.execute(text("DELETE FROM emission_factors"))

        await self.session.commit()
        logger.info("Existing data cleared")

    async def seed_emission_factors(self) -> int:
        """
        Load emission factors from Emission_Factors.csv.

        Returns:
            Number of emission factors created
        """
        csv_file = self.data_dir / "Emission_Factors.csv"
        if not csv_file.exists():
            logger.warning(f"File not found: {csv_file}")
            return 0

        logger.info(f"Loading emission factors from {csv_file}")
        repo = EmissionFactorRepository(self.session)
        count = 0

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse category (can be empty)
                    category = None
                    if row.get("Category") and row["Category"].strip():
                        try:
                            category = int(row["Category"])
                        except ValueError:
                            pass

                    factor = await repo.create(
                        activity_type=row["Activity"],
                        lookup_identifier=row["Lookup identifiers"],
                        unit=row["Unit"],
                        co2e_factor=Decimal(row["CO2e"]),
                        scope=int(row["Scope"]),
                        category=category,
                    )
                    count += 1

                except Exception as e:
                    logger.warning(f"Failed to create emission factor from row {row}: {e}")
                    continue

        logger.info(f"Created {count} emission factors")
        return count

    async def seed_electricity_activities(self) -> int:
        """
        Load electricity activities from Electricity.csv.

        Returns:
            Number of electricity activities created
        """
        csv_file = self.data_dir / "Electricity.csv"
        if not csv_file.exists():
            logger.warning(f"File not found: {csv_file}")
            return 0

        logger.info(f"Loading electricity activities from {csv_file}")
        repo = ElectricityActivityRepository(self.session)
        count = 0

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse date (format: DD/MM/YYYY)
                    date_str = row["Date"]
                    activity_date = datetime.strptime(date_str, "%d/%m/%Y").date()

                    # Parse usage (remove commas)
                    usage_str = row["Electricity Usage"].replace(",", "")
                    usage_kwh = Decimal(usage_str)

                    await repo.create(
                        activity_type=ActivityType.ELECTRICITY,
                        date=activity_date,
                        country=row["Country"],
                        usage_kwh=usage_kwh,
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to create electricity activity from row {row}: {e}"
                    )
                    continue

        logger.info(f"Created {count} electricity activities")
        return count

    async def seed_air_travel_activities(self) -> int:
        """
        Load air travel activities from Air_Travel.csv.

        Returns:
            Number of air travel activities created
        """
        csv_file = self.data_dir / "Air_Travel.csv"
        if not csv_file.exists():
            logger.warning(f"File not found: {csv_file}")
            return 0

        logger.info(f"Loading air travel activities from {csv_file}")
        repo = AirTravelActivityRepository(self.session)
        count = 0

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse date (format: DD/MM/YYYY)
                    date_str = row["Date"]
                    activity_date = datetime.strptime(date_str, "%d/%m/%Y").date()

                    # Parse distance (remove commas and quotes)
                    distance_str = row["Distance travelled"].replace(",", "").replace(
                        '"', ""
                    )
                    distance_miles = Decimal(distance_str)
                    distance_km = UnitConverter.miles_to_km(distance_miles)

                    await repo.create(
                        activity_type=ActivityType.AIR_TRAVEL,
                        date=activity_date,
                        distance_miles=distance_miles,
                        distance_km=distance_km,
                        flight_range=row["Flight range"],
                        passenger_class=row["Passenger class"],
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to create air travel activity from row {row}: {e}"
                    )
                    continue

        logger.info(f"Created {count} air travel activities")
        return count

    async def seed_goods_services_activities(self) -> int:
        """
        Load goods/services activities from Purchased_Goods_and_Services.csv.

        Returns:
            Number of goods/services activities created
        """
        csv_file = self.data_dir / "Purchased_Goods_and_Services.csv"
        if not csv_file.exists():
            logger.warning(f"File not found: {csv_file}")
            return 0

        logger.info(f"Loading goods/services activities from {csv_file}")
        repo = GoodsServicesActivityRepository(self.session)
        count = 0

        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse date (format: DD/MM/YYYY)
                    date_str = row["Date"]
                    activity_date = datetime.strptime(date_str, "%d/%m/%Y").date()

                    # Parse spend (remove currency symbols and commas)
                    spend_str = (
                        row["Spend"].replace("£", "").replace(",", "").replace('"', "")
                    )
                    spend_gbp = Decimal(spend_str)

                    await repo.create(
                        activity_type=ActivityType.GOODS_SERVICES,
                        date=activity_date,
                        supplier_category=row["Supplier category"],
                        spend_gbp=spend_gbp,
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to create goods/services activity from row {row}: {e}"
                    )
                    continue

        logger.info(f"Created {count} goods/services activities")
        return count

    async def _calculate_all_emissions(self) -> dict[str, Any]:
        """
        Calculate emissions for all activities without emission results.

        Uses streaming mode for efficient processing of large datasets.

        Returns:
            Dictionary with calculation statistics
        """
        service = EmissionCalculationService(self.session)

        # Use streaming mode to handle unlimited activities efficiently
        logger.info("Calculating emissions using streaming mode...")
        summary = await service.calculate_all_pending(
            batch_size=100,  # Process 100 activities at a time
            use_streaming=True,  # Enable streaming for unlimited scale
        )

        # Extract statistics for backward compatibility
        stats = summary["statistics"]
        return {
            "calculated": stats["total_processed"],
            "total": stats["total_activities"],
            "errors": summary["errors"],
            "total_co2e_tonnes": stats["total_co2e_tonnes"],
            "by_activity_type": stats["by_activity_type"],
        }
