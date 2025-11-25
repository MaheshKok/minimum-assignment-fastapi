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
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create Rich console
console = Console()


def print_header(text: str, style: str = "bold cyan"):
    """Print a formatted header using Rich Panel."""
    console.print(
        Panel(
            Text(text, justify="center", style=style),
            border_style="cyan",
            padding=(1, 2),
        )
    )


def print_config(args):
    """Print configuration details."""
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("Setting", style="bold yellow")
    config_table.add_column("Value", style="green")

    config_table.add_row("📁 Data Directory", args.data_dir)
    config_table.add_row("🗑️  Clear Existing", "Yes" if args.clear else "No")
    config_table.add_row(
        "🧮 Skip Calculations", "Yes" if args.skip_calculations else "No"
    )

    console.print(config_table)
    console.print()


def print_stats(stats: dict):
    """Print seeding statistics using Rich Table."""
    print_header("SEEDING STATISTICS", "bold green")

    # Main statistics table
    stats_table = Table(show_header=True, box=None, padding=(0, 2))
    stats_table.add_column("Category", style="bold cyan", width=30)
    stats_table.add_column("Count", justify="right", style="bold green")

    stats_table.add_row("📊 Emission Factors", str(stats["emission_factors"]))
    stats_table.add_row(
        "⚡ Electricity Activities", str(stats["electricity_activities"])
    )
    stats_table.add_row("✈️  Air Travel Activities", str(stats["air_travel_activities"]))
    stats_table.add_row(
        "📦 Goods/Services Activities", str(stats["goods_services_activities"])
    )
    stats_table.add_row("🧮 Emission Results", str(stats["emission_results"]))

    console.print(stats_table)
    console.print()

    # Calculate totals
    total_activities = (
        stats["electricity_activities"]
        + stats["air_travel_activities"]
        + stats["goods_services_activities"]
    )

    # Summary panel
    summary = Table(show_header=False, box=None, padding=(0, 2))
    summary.add_column("Label", style="bold yellow")
    summary.add_column("Value", style="bold magenta")
    summary.add_row("📈 Total Activities", str(total_activities))

    console.print(summary)

    # Show errors if any
    if stats.get("errors"):
        console.print()
        console.print(
            Panel(
                f"[yellow]⚠️  {len(stats['errors'])} errors occurred during seeding[/yellow]",
                border_style="yellow",
            )
        )
        for i, error in enumerate(stats["errors"][:5], 1):
            console.print(f"  {i}. [dim]{error}[/dim]")
        if len(stats["errors"]) > 5:
            console.print(f"  [dim]... and {len(stats['errors']) - 5} more[/dim]")

    console.print()


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

    # Print beautiful header
    print_header("DATABASE SEEDING", "bold cyan")
    print_config(args)

    try:
        # Initialize database
        config = get_config(ConfigFile.DEVELOPMENT)
        async_db_url = get_db_url(config)
        Database.init(async_db_url, engine_kw=engine_kw)
        logger.info("Database initialized")

        # Start seeding with progress indication
        with console.status(
            "[bold cyan]Seeding database...", spinner="dots"
        ) as status:
            async with DatabaseSeeder(data_dir=args.data_dir) as seeder:
                logger.info("Starting database seeding")

                # Update status for different phases
                status.update("[bold yellow]Loading emission factors...")
                stats = await seeder.seed_all(
                    clear_existing=args.clear,
                    skip_calculations=args.skip_calculations,
                )

        # Print beautiful statistics
        print_stats(stats)

        # Success message
        console.print(
            Panel(
                Text("✅ SEEDING COMPLETED SUCCESSFULLY", justify="center"),
                border_style="bold green",
                style="bold green",
            )
        )

    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)

        # Error message
        console.print()
        console.print(
            Panel(
                f"[bold red]❌ SEEDING FAILED[/bold red]\n\n[red]{e!s}[/red]",
                border_style="bold red",
            )
        )
        console.print()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
