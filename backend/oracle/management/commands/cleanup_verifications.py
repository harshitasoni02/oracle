"""
Management command to clean up PredictionVerification records.

Usage:
    # Delete all verification records (full reset)
    python manage.py cleanup_verifications --all

    # Delete records before a specific date
    python manage.py cleanup_verifications --before 2025-07-07

    # Delete records with previous_price = 0
    python manage.py cleanup_verifications --bad-prices

    # Dry-run (show what would be deleted without actually deleting)
    python manage.py cleanup_verifications --before 2025-07-07 --dry-run
"""

from __future__ import annotations

from datetime import datetime, date

from django.core.management.base import BaseCommand
from django.utils import timezone

from oracle.models import PredictionVerification


class Command(BaseCommand):
    help = "Clean up PredictionVerification records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Delete ALL verification records",
        )
        parser.add_argument(
            "--before",
            type=str,
            help="Delete records with prediction_date before this date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--bad-prices",
            action="store_true",
            help="Delete records where previous_price = 0",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        qs = PredictionVerification.objects.all()
        source_desc = "all records"

        if options["all"]:
            pass  # qs already = all

        elif options["before"]:
            try:
                cutoff = datetime.strptime(options["before"], "%Y-%m-%d")
                cutoff = timezone.make_aware(cutoff)
            except ValueError:
                self.stderr.write("Invalid date format. Use YYYY-MM-DD (e.g. 2025-07-07)")
                return
            qs = qs.filter(prediction_date__lt=cutoff)
            source_desc = f"records before {options['before']}"

        elif options["bad_prices"]:
            qs = qs.filter(previous_price=0)
            source_desc = "records with previous_price = 0"

        else:
            self.stdout.write(self.style.WARNING(
                "No filter specified. Use --all, --before YYYY-MM-DD, or --bad-prices"
            ))
            return

        count = qs.count()
        if count == 0:
            self.stdout.write(f"No {source_desc} found. Nothing to delete.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[DRY-RUN] Would delete {count} {source_desc}"
            )
            return

        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} {source_desc}")
        )
