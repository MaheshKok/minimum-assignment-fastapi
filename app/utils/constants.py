"""
Application constants following kkb_fastapi pattern.
"""


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


class Scope:
    """GHG Protocol Scope constants."""
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3


class Category:
    """GHG Protocol Scope 3 Category constants."""
    CATEGORY_1 = 1  # Purchased Goods and Services
    CATEGORY_6 = 6  # Business Travel


# Unit conversion constants
MILES_TO_KM = 1.60934
