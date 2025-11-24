"""
Air travel emissions calculator service - async version.

Calculates CO2e emissions from business air travel.
"""

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import AirTravelActivityDBModel, EmissionResultDBModel
from app.services.calculators.factor_matcher import FactorMatcher
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType

logger = logging.getLogger(__name__)


class TravelCalculator:
    """
    Service for calculating emissions from air travel.

    Handles Scope 3, Category 6 emissions based on distance and flight class.
    """

    def __init__(self, session: AsyncSession):
        """Initialize calculator with database session."""
        self.session = session
        self.factor_matcher = FactorMatcher(session)

    async def calculate(
        self,
        activity: AirTravelActivityDBModel,
        fuzzy_threshold: int = 80,
    ) -> EmissionResultDBModel | None:
        """
        Calculate CO2e emissions from air travel activity.

        Args:
            activity: AirTravelActivityDBModel instance
            fuzzy_threshold: Minimum fuzzy match threshold (0-100)

        Returns:
            EmissionResultDBModel instance if calculation successful, None otherwise

        Formula:
            CO2e (tonnes) = distance_km * emission_factor / 1000

        Example:
            >>> activity = AirTravelActivityDBModel(
            ...     distance_miles=Decimal("500.00"),
            ...     flight_range="Short-haul",
            ...     passenger_class="Economy class"
            ... )
            >>> result = await calculator.calculate(activity)
            >>> print(f"Emissions: {result.co2e_tonnes} tonnes")
        """
        logger.info(
            f"Calculating air travel emissions for {activity.distance_km} km "
            f"({activity.flight_range}, {activity.passenger_class})"
        )

        # Ensure distance_km is populated (convert from miles if needed)
        if activity.distance_km is None or activity.distance_km == 0:
            if activity.distance_miles is not None and activity.distance_miles > 0:
                activity.distance_km = UnitConverter.miles_to_km(activity.distance_miles)
                await self.session.flush()

        # Only reject if BOTH distances are None or missing
        if activity.distance_km is None and activity.distance_miles is None:
            logger.error(f"No distance information available for air travel activity {activity.id}")
            return None

        # If we have a zero distance, proceed with 0 emissions
        if activity.distance_km == 0 or activity.distance_km is None:
            logger.info(
                f"Zero-distance flight for activity {activity.id} - calculating 0 emissions"
            )
            if activity.distance_km is None:
                activity.distance_km = Decimal("0")
                await self.session.flush()

        # Match emission factor using specialized air travel matcher
        match_result = await self.factor_matcher.match_air_travel(
            activity.flight_range,
            activity.passenger_class,
            threshold=fuzzy_threshold,
        )

        if match_result is None:
            logger.error(
                f"No emission factor found for air travel: "
                f"{activity.flight_range}, {activity.passenger_class}"
            )
            return None

        emission_factor, confidence = match_result

        # Calculate emissions
        # Formula: km * kgCO2e/km / 1000 = tonnes CO2e
        distance = UnitConverter.normalize_number(activity.distance_km)
        factor = emission_factor.co2e_factor

        co2e_tonnes = (distance * factor) / Decimal("1000")

        # Create emission result
        result = EmissionResultDBModel(
            activity_type=ActivityType.AIR_TRAVEL,
            activity_id=activity.id,
            emission_factor_id=emission_factor.id,
            co2e_tonnes=co2e_tonnes,
            confidence_score=confidence,
            calculation_metadata={
                "distance_km": str(distance),
                "distance_miles": (
                    str(activity.distance_miles) if activity.distance_miles is not None else None
                ),
                "flight_range": activity.flight_range,
                "passenger_class": activity.passenger_class,
                "matched_identifier": emission_factor.lookup_identifier,
                "emission_factor_value": str(factor),
                "unit": emission_factor.unit,
                "calculation_method": "exact" if confidence == Decimal("1.0") else "fuzzy",
            },
        )

        self.session.add(result)
        await self.session.flush()

        logger.info(
            f"Calculated {co2e_tonnes} tonnes CO2e for air travel activity "
            f"(confidence: {confidence})"
        )

        return result
