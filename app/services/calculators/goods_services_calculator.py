"""
Goods and services emissions calculator service - async version.

Calculates CO2e emissions from purchased goods and services.
"""

import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import EmissionResultDBModel, GoodsServicesActivityDBModel
from app.services.calculators.factor_matcher import FactorMatcher
from app.services.calculators.unit_converter import UnitConverter
from app.utils.constants import ActivityType

logger = logging.getLogger(__name__)


class GoodsServicesCalculator:
    """
    Service for calculating emissions from purchased goods and services.

    Handles Scope 3, Category 1 emissions based on spend-based method.
    """

    def __init__(self, session: AsyncSession):
        """Initialize calculator with database session."""
        self.session = session
        self.factor_matcher = FactorMatcher(session)

    async def calculate(
        self,
        activity: GoodsServicesActivityDBModel,
        fuzzy_threshold: int = 80,
    ) -> Optional[EmissionResultDBModel]:
        """
        Calculate CO2e emissions from goods/services activity.

        Args:
            activity: GoodsServicesActivityDBModel instance
            fuzzy_threshold: Minimum fuzzy match threshold (0-100)

        Returns:
            EmissionResultDBModel instance if calculation successful, None otherwise

        Formula:
            CO2e (tonnes) = spend_gbp * emission_factor / 1000

        Example:
            >>> activity = GoodsServicesActivityDBModel(
            ...     supplier_category="Paper Products",
            ...     spend_gbp=Decimal("5000.00")
            ... )
            >>> result = await calculator.calculate(activity)
            >>> print(f"Emissions: {result.co2e_tonnes} tonnes")
        """
        logger.info(
            f"Calculating goods/services emissions for £{activity.spend_gbp} "
            f"in {activity.supplier_category}"
        )

        # Match emission factor
        match_result = await self.factor_matcher.match_with_fallback(
            ActivityType.GOODS_SERVICES,
            activity.supplier_category,
            threshold=fuzzy_threshold,
        )

        if match_result is None:
            logger.error(
                f"No emission factor found for goods/services category: "
                f"{activity.supplier_category}"
            )
            return None

        emission_factor, confidence = match_result

        # Calculate emissions
        # Formula: GBP * kgCO2e/GBP / 1000 = tonnes CO2e
        spend = UnitConverter.normalize_number(activity.spend_gbp)
        factor = emission_factor.co2e_factor

        co2e_tonnes = (spend * factor) / Decimal("1000")

        # Create emission result
        result = EmissionResultDBModel(
            activity_type=ActivityType.GOODS_SERVICES,
            activity_id=activity.id,
            emission_factor_id=emission_factor.id,
            co2e_tonnes=co2e_tonnes,
            confidence_score=confidence,
            calculation_metadata={
                "spend_gbp": str(spend),
                "supplier_category": activity.supplier_category,
                "matched_category": emission_factor.lookup_identifier,
                "emission_factor_value": str(factor),
                "unit": emission_factor.unit,
                "calculation_method": "exact" if confidence == Decimal("1.0") else "fuzzy",
            },
        )

        self.session.add(result)
        await self.session.flush()

        logger.info(
            f"Calculated {co2e_tonnes} tonnes CO2e for goods/services activity "
            f"(confidence: {confidence})"
        )

        return result
