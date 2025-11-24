"""
Unit conversion utilities for emissions calculations.

Provides conversions between different measurement units.
Converted from Django synchronous to async-compatible (stateless utilities).
"""

from decimal import Decimal


class UnitConverter:
    """
    Unit conversion service.

    Provides methods to convert between different units of measurement
    used in emissions calculations.
    """

    # Conversion constants
    MILES_TO_KM = Decimal("1.60934")
    KM_TO_MILES = Decimal("0.621371")
    TONNES_TO_KG = Decimal("1000")
    KG_TO_TONNES = Decimal("0.001")

    @staticmethod
    def miles_to_km(miles: float | Decimal) -> Decimal:
        """
        Convert miles to kilometers.

        Args:
            miles: Distance in miles

        Returns:
            Distance in kilometers as Decimal

        Example:
            >>> UnitConverter.miles_to_km(100)
            Decimal('160.934')
        """

        if isinstance(miles, float):
            miles = Decimal(str(miles))
        return miles * UnitConverter.MILES_TO_KM

    @staticmethod
    def km_to_miles(km: float | Decimal) -> Decimal:
        """
        Convert kilometers to miles.

        Args:
            km: Distance in kilometers

        Returns:
            Distance in miles as Decimal
        """

        if isinstance(km, float):
            km = Decimal(str(km))
        return km * UnitConverter.KM_TO_MILES

    @staticmethod
    def tonnes_to_kg(tonnes: float | Decimal) -> Decimal:
        """
        Convert tonnes to kilograms.

        Args:
            tonnes: Mass in tonnes

        Returns:
            Mass in kilograms as Decimal
        """

        if isinstance(tonnes, float):
            tonnes = Decimal(str(tonnes))
        return tonnes * UnitConverter.TONNES_TO_KG

    @staticmethod
    def kg_to_tonnes(kg: float | Decimal) -> Decimal:
        """
        Convert kilograms to tonnes.

        Args:
            kg: Mass in kilograms

        Returns:
            Mass in tonnes as Decimal
        """

        if isinstance(kg, float):
            kg = Decimal(str(kg))
        return kg * UnitConverter.KG_TO_TONNES

    @staticmethod
    def normalize_number(value: str | float | Decimal) -> Decimal:
        """
        Normalize a number value to Decimal.

        Handles string inputs with commas, floats, and existing Decimals.

        Args:
            value: Number value in various formats

        Returns:
            Normalized Decimal value

        Example:
            >>> UnitConverter.normalize_number("1,234.56")
            Decimal('1234.56')
        """

        if isinstance(value, Decimal):
            return value

        if isinstance(value, str):
            # Remove commas from string numbers
            value = value.replace(",", "")

        return Decimal(str(value))
