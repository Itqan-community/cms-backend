"""Management command to prune old audit history records from the audit database (ITQ-36 / #434)."""

from datetime import timedelta

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

CORE_SOVEREIGN_MODELS = {
    "Asset",
    "AssetVersion",
    "License",
    "Publisher",
    "User",
}

DEFAULT_PRUNABLE_MODELS = {
    "AssetAccessRequest",
    "ContentIssueReport",
    "PublisherMemberInvitation",
    "MemberLanguage",
}


class Command(BaseCommand):
    help = (
        "Prunes historical audit records older than the specified retention window (default: 365 days). "
        "Core sovereign entities (Asset, AssetVersion, License, Publisher, User) are protected and skipped "
        "unless --force-core is explicitly supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Age threshold in days. Historical records older than this will be pruned (default: 365).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the pruning process and display match counts without deleting any records.",
        )
        parser.add_argument(
            "--models",
            type=str,
            default=None,
            help="Comma-separated list of model names or app_label.Model names to prune (e.g. 'AssetAccessRequest,ContentIssueReport').",
        )
        parser.add_argument(
            "--force-core",
            action="store_true",
            help="Force pruning on core sovereign entities (Asset, AssetVersion, License, Publisher, User).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        models_filter = options["models"]
        force_core = options["force_core"]

        if days < 1:
            raise CommandError("--days must be a positive integer.")

        cutoff_date = timezone.now() - timedelta(days=days)
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"{'[DRY RUN] ' if dry_run else ''}Evaluating audit history retention (Cutoff: {cutoff_date.isoformat()}, Window: {days} days)..."
            )
        )

        # Discover all models tracked by simple-history
        tracked_models = [m for m in apps.get_models() if hasattr(m, "history")]

        if models_filter is not None:
            target_selectors = [m.strip().lower() for m in models_filter.split(",") if m.strip()]
            if not target_selectors:
                raise CommandError("--models was provided but contains no valid model names.")

            valid_names = {m.__name__.lower() for m in tracked_models}
            valid_labels = {m._meta.label_lower for m in tracked_models}
            valid_all = valid_names | valid_labels

            invalid_selectors = [s for s in target_selectors if s not in valid_all]
            if invalid_selectors:
                raise CommandError(
                    f"The following model selector(s) do not match any tracked model: {', '.join(sorted(invalid_selectors))}"
                )
            target_model_names = set(target_selectors)
        else:
            # Default retention policy: prune only documented Tier 2 operational models
            target_model_names = {m.lower() for m in DEFAULT_PRUNABLE_MODELS}
            self.stdout.write(
                "No --models specified; defaulting to documented Tier 2 operational models "
                f"({', '.join(sorted(DEFAULT_PRUNABLE_MODELS))})."
            )

        total_pruned = 0
        total_scanned = 0

        for model in tracked_models:
            model_name = model.__name__
            full_label = model._meta.label_lower

            if target_model_names and (
                model_name.lower() not in target_model_names and full_label not in target_model_names
            ):
                continue

            total_scanned += 1

            # Retention policy enforcement: skip core sovereign models unless explicitly forced
            if model_name in CORE_SOVEREIGN_MODELS and not force_core:
                self.stdout.write(
                    f"  - {model_name}: Protected core entity (retained indefinitely per retention policy; skipped)"
                )
                continue

            manager_attr = getattr(model._meta, "simple_history_manager_attribute", "history")
            history_manager = getattr(model, manager_attr, None)
            if history_manager is None:
                continue

            # Query historical records older than cutoff, always preserving tombstone deletion snapshots
            old_records = history_manager.filter(history_date__lt=cutoff_date).exclude(history_type="-")

            # Protect active/open workflow instances from losing their audit history before closure
            if any(f.name == "status" for f in model._meta.fields):
                open_pks = set(
                    model.objects.filter(status__in=["pending", "under_review"]).values_list(
                        model._meta.pk.name, flat=True
                    )
                )
                if open_pks:
                    old_records = old_records.exclude(**{f"{model._meta.pk.name}__in": open_pks})

            count = old_records.count()

            if count == 0:
                self.stdout.write(f"  - {model_name}: 0 eligible records")
                continue

            if dry_run:
                self.stdout.write(self.style.WARNING(f"  - {model_name}: {count} records would be pruned"))
                total_pruned += count
            else:
                # Delete old historical records
                deleted_count, _ = old_records.delete()
                self.stdout.write(self.style.SUCCESS(f"  - {model_name}: Successfully pruned {deleted_count} records"))
                total_pruned += deleted_count

        action_word = "would be pruned" if dry_run else "pruned"
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                f"\nTotal: {total_pruned} records {action_word} across {total_scanned} tracked models."
            )
        )
