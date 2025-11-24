"""
Electricity emissions calculator service - async version.

Calculates CO2e emissions from electricity consumption.
"""

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import ElectricityActivityDBModel, EmissionResultDBModel
from app.services.calculators.factor_matcher import FactorMatcher
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType

logger = logging.getLogger(__name__)


class ElectricityCalculator:
    """
    Service for calculating emissions from electricity consumption.

    Handles Scope 2 emissions based on country-specific grid factors.
    """

    def __init__(self, session: AsyncSession):
        """Initialize calculator with database session."""
        self.session = session
        self.factor_matcher = FactorMatcher(session)

    async def calculate(
        self,
        activity: ElectricityActivityDBModel,
        fuzzy_threshold: int = 80,
    ) -> EmissionResultDBModel | None:
        """
        Calculate CO2e emissions from electricity activity.

        Args:
            activity: ElectricityActivityDBModel instance
            fuzzy_threshold: Minimum fuzzy match threshold (0-100)

        Returns:
            EmissionResultDBModel instance if calculation successful, None otherwise

        Formula:
            CO2e (tonnes) = usage_kwh * emission_factor / 1000

        Example:
            >>> activity = ElectricityActivityDBModel(
            ...     country="United Kingdom",
            ...     usage_kwh=Decimal("1000.00")
            ... )
            >>> result = await calculator.calculate(activity)
            >>> print(f"Emissions: {result.co2e_tonnes} tonnes")
        """
        logger.info(
            f"Calculating electricity emissions for {activity.usage_kwh} kWh "
            f"in {activity.country}"
        )

        # Match emission factor
        match_result = await self.factor_matcher.match_with_fallback(
            ActivityType.ELECTRICITY,
            activity.country,
            threshold=fuzzy_threshold,
        )

        if match_result is None:
            logger.error(f"No emission factor found for electricity in {activity.country}")
            return None

        emission_factor, confidence = match_result

        # Calculate emissions
        # Formula: kWh * kgCO2e/kWh / 1000 = tonnes CO2e
        usage = UnitConverter.normalize_number(activity.usage_kwh)
        factor = emission_factor.co2e_factor

        co2e_tonnes = (usage * factor) / Decimal("1000")

        # Create emission result
        result = EmissionResultDBModel(
            activity_type=ActivityType.ELECTRICITY,
            activity_id=activity.id,
            emission_factor_id=emission_factor.id,
            co2e_tonnes=co2e_tonnes,
            confidence_score=confidence,
            calculation_metadata={
                "usage_kwh": str(usage),
                "country": activity.country,
                "matched_country": emission_factor.lookup_identifier,
                "emission_factor_value": str(factor),
                "unit": emission_factor.unit,
                "calculation_method": "exact" if confidence == Decimal("1.0") else "fuzzy",
            },
        )

        self.session.add(result)
        await self.session.flush()

        logger.info(
            f"Calculated {co2e_tonnes} tonnes CO2e for electricity activity "
            f"(confidence: {confidence})"
        )

        return result
