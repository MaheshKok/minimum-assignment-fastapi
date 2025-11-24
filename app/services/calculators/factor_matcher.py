"""
Emission factor matching utilities - async version.

Provides exact and fuzzy matching for emission factors.
Converted from Django ORM to SQLAlchemy async.
"""

import logging
from decimal import Decimal
from functools import lru_cache
from typing import Optional, Tuple

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import EmissionFactorDBModel
from app.utils.constants import ActivityType

logger = logging.getLogger(__name__)


class FactorMatcher:
    """
    Service for matching activity data to emission factors.

    Supports exact matching and fuzzy matching with confidence scoring.
    """

    # Default fuzzy matching threshold (80%)
    DEFAULT_THRESHOLD = 80

    def __init__(self, session: AsyncSession):
        """
        Initialize factor matcher with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def exact_match(
        self,
        activity_type: str,
        lookup_identifier: str,
    ) -> Optional[EmissionFactorDBModel]:
        """
        Find exact emission factor match.

        Args:
            activity_type: Type of activity
            lookup_identifier: Identifier to match

        Returns:
            EmissionFactorDBModel if found, None otherwise
        """
        try:
            stmt = select(EmissionFactorDBModel).where(
                EmissionFactorDBModel.activity_type == activity_type,
                EmissionFactorDBModel.lookup_identifier.ilike(lookup_identifier),
            )
            result = await self.session.execute(stmt)
            factor = result.scalars().first()

            if factor:
                logger.debug(f"Exact match found for {activity_type}: {lookup_identifier}")
            else:
                logger.debug(f"No exact match for {activity_type}: {lookup_identifier}")

            return factor

        except Exception as e:
            logger.error(f"Error in exact_match: {e}")
            return None

    async def fuzzy_match(
        self,
        activity_type: str,
        lookup_identifier: str,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> Optional[Tuple[EmissionFactorDBModel, Decimal]]:
        """
        Find emission factor using fuzzy matching.

        Uses rapidfuzz to find the best match above the threshold.

        Args:
            activity_type: Type of activity
            lookup_identifier: Identifier to match
            threshold: Minimum similarity score (0-100)

        Returns:
            Tuple of (EmissionFactorDBModel, confidence_score) if match found, None otherwise
        """
        # Get all factors for this activity type
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.activity_type == activity_type
        )
        result = await self.session.execute(stmt)
        factors = result.scalars().all()

        if not factors:
            logger.warning(f"No emission factors found for {activity_type}")
            return None

        # Build dict of identifier -> factor
        choices = {factor.lookup_identifier: factor for factor in factors}

        # Find best match using token_sort_ratio (handles word order)
        result = process.extractOne(
            lookup_identifier,
            choices.keys(),
            scorer=fuzz.token_sort_ratio,
        )

        if result is None:
            logger.warning(f"No fuzzy match found for {activity_type}: {lookup_identifier}")
            return None

        matched_identifier, score, _ = result

        if score < threshold:
            logger.info(
                f"Fuzzy match score {score} below threshold {threshold} "
                f"for {activity_type}: {lookup_identifier}"
            )
            return None

        # Get the matched factor
        factor = choices[matched_identifier]

        # Convert score to confidence (0.0 - 1.0)
        confidence = Decimal(str(score)) / Decimal("100")

        logger.info(
            f"Fuzzy matched '{lookup_identifier}' to '{matched_identifier}' "
            f"with {score}% confidence for {activity_type}"
        )

        return factor, confidence

    async def match_with_fallback(
        self,
        activity_type: str,
        lookup_identifier: str,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> Optional[Tuple[EmissionFactorDBModel, Decimal]]:
        """
        Match emission factor with exact match first, then fuzzy fallback.

        Args:
            activity_type: Type of activity
            lookup_identifier: Identifier to match
            threshold: Minimum fuzzy match threshold

        Returns:
            Tuple of (EmissionFactorDBModel, confidence_score)
        """
        # Try exact match first
        factor = await self.exact_match(activity_type, lookup_identifier)
        if factor:
            logger.debug(f"Exact match found for {activity_type}: {lookup_identifier}")
            return factor, Decimal("1.0")

        # Fall back to fuzzy matching
        logger.debug(f"No exact match, trying fuzzy match for {activity_type}: {lookup_identifier}")
        result = await self.fuzzy_match(activity_type, lookup_identifier, threshold)

        if result is None:
            logger.error(
                f"No match found (exact or fuzzy) for {activity_type}: {lookup_identifier}"
            )
            return None

        return result

    async def match_air_travel(
        self,
        flight_range: str,
        passenger_class: str,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> Optional[Tuple[EmissionFactorDBModel, Decimal]]:
        """
        Match emission factor for air travel.

        Air travel requires matching on two fields: flight range and passenger class.
        The lookup identifier is formatted as: "Flight Range, Passenger Class"

        Args:
            flight_range: Flight range (e.g., "Short-haul", "Long-haul")
            passenger_class: Passenger class (e.g., "Economy", "Business class")
            threshold: Minimum fuzzy match threshold

        Returns:
            Tuple of (EmissionFactorDBModel, confidence_score)
        """
        # Normalize passenger class (handle "Business Class" vs "Business class")
        passenger_class_normalized = passenger_class.strip()

        # Try exact combination first
        lookup_key = f"{flight_range}, {passenger_class_normalized}"

        result = await self.match_with_fallback(
            ActivityType.AIR_TRAVEL,
            lookup_key,
            threshold,
        )

        if result:
            return result

        # Try partial matches if exact combination fails
        stmt = select(EmissionFactorDBModel).where(
            EmissionFactorDBModel.activity_type == ActivityType.AIR_TRAVEL
        )
        result_factors = await self.session.execute(stmt)
        factors = result_factors.scalars().all()

        for factor in factors:
            identifier = factor.lookup_identifier.lower()
            if (
                flight_range.lower() in identifier
                and passenger_class_normalized.lower() in identifier
            ):
                logger.info(
                    f"Partial match found: {factor.lookup_identifier} "
                    f"for {flight_range}, {passenger_class_normalized}"
                )
                return factor, Decimal("0.9")

        logger.error(f"No match found for air travel: {flight_range}, {passenger_class_normalized}")
        return None
