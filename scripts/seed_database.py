#!/usr/bin/env python3
"""
CLI script to seed the database with test data from CSV files.

Usage:
    # Basic seeding
    python scripts/seed_database.py

    # Clear existing data before seeding
    python scripts/seed_database.py --clear

    # Seed without calculating emissions
    python scripts/seed_database.py --skip-calculations

    # Use a different data directory
    python scripts/seed_database.py --data-dir path/to/csv/files

    # Using uv
    uv run python scripts/seed_database.py --clear
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_config
from app.database.base import engine_kw, get_db_url
from app.database.session_manager.db_session import Database
from app.services.seed_database import DatabaseSeeder
from app.utils.constants import ConfigFile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_stats(stats: dict):
    """Print seeding statistics."""
    print_header("SEEDING STATISTICS")

    print(f"📊 Emission Factors:       {stats['emission_factors']}")
    print(f"⚡ Electricity Activities:  {stats['electricity_activities']}")
    print(f"✈️  Air Travel Activities:   {stats['air_travel_activities']}")
    print(f"📦 Goods/Services Activities: {stats['goods_services_activities']}")
    print(f"🧮 Emission Results:       {stats['emission_results']}")

    if stats.get("errors"):
        print(f"\n⚠️  Errors: {len(stats['errors'])}")
        for error in stats["errors"][:5]:  # Show first 5 errors
            print(f"   - {error}")
        if len(stats["errors"]) > 5:
            print(f"   ... and {len(stats['errors']) - 5} more")

    total_activities = (
        stats["electricity_activities"]
        + stats["air_travel_activities"]
        + stats["goods_services_activities"]
    )
    print(f"\n📈 Total Activities:       {total_activities}")
    print()


async def main():
    """Main entry point for the seeding script."""
    parser = argparse.ArgumentParser(
        description="Seed the database with test data from CSV files"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before seeding",
    )
    parser.add_argument(
        "--skip-calculations",
        action="store_true",
        help="Skip automatic emission calculations",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="app/test/test_data",
        help="Directory containing CSV files (default: app/test/test_data)",
    )

    args = parser.parse_args()

    print_header("DATABASE SEEDING")
    print(f"Data Directory: {args.data_dir}")
    print(f"Clear Existing: {args.clear}")
    print(f"Skip Calculations: {args.skip_calculations}")
    print()

    try:
        # Initialize database
        config = get_config(ConfigFile.DEVELOPMENT)
        async_db_url = get_db_url(config)
        Database.init(async_db_url, engine_kw=engine_kw)
        logger.info("Database initialized")

        async with DatabaseSeeder(data_dir=args.data_dir) as seeder:
            logger.info("Starting database seeding")

            stats = await seeder.seed_all(
                clear_existing=args.clear,
                skip_calculations=args.skip_calculations,
            )

            print_stats(stats)
            print_header("✅ SEEDING COMPLETED SUCCESSFULLY")

    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        print_header("❌ SEEDING FAILED")
        print(f"Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
