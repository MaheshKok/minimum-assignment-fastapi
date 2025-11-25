"""
Application constants following kkb_fastapi pattern.
"""
from enum import Enum


class ConfigFile:
    """Configuration file paths."""
    PRODUCTION = "production.toml"
    DEVELOPMENT = "development.toml"
    TEST = "test.toml"


class ActivityType:
    """Activity type constants matching Django choices."""
    ELECTRICITY = "Electricity"
    AIR_TRAVEL = "Air Travel"
    GOODS_SERVICES = "Purchased Goods and Services"


class ActivityTypeEnum(str, Enum):
    """Activity type enum for API parameters."""
    ELECTRICITY = "Electricity"
    AIR_TRAVEL = "Air Travel"
    GOODS_SERVICES = "Purchased Goods and Services"


class Scope:
    """GHG Protocol Scope constants."""
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3


class ScopeEnum(int, Enum):
    """GHG Protocol Scope enum for API parameters."""
    SCOPE_2 = 2
    SCOPE_3 = 3


class CategoryEnum(int, Enum):
    """GHG Protocol Scope 3 Category enum for API parameters."""
    CATEGORY_1 = 1  # Purchased Goods and Services
    CATEGORY_6 = 6  # Business Travel


class SortOrderEnum(str, Enum):
    """Sort order enum for API parameters."""
    ASC = "asc"
    DESC = "desc"


# Unit conversion constants
MILES_TO_KM = 1.60934
