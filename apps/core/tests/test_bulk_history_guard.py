"""AST regression tests ensuring no tracked models bypass simple_history on bulk operations (ITQ-34 / #432)."""

import ast
import os
from pathlib import Path

from django.test import SimpleTestCase

from apps.core.tests.test_tracked_models_history import TRACKED_MODELS

TRACKED_MODEL_NAMES = {model.__name__ for model in TRACKED_MODELS}


def _get_root_name(node: ast.AST) -> str | None:
    """Traverses chained attribute and call expressions to extract the root identifier name.

    E.g.:
        AssetVersionEntry.objects.bulk_create -> 'AssetVersionEntry'
        Asset.objects.filter(...).update -> 'Asset'
    """
    curr = node
    while isinstance(curr, ast.Attribute | ast.Call):
        if isinstance(curr, ast.Attribute):
            curr = curr.value
        elif isinstance(curr, ast.Call):
            curr = curr.func
    if isinstance(curr, ast.Name):
        return curr.id
    return None


def scan_tree_for_bulk_violations(
    tree: ast.AST,
    tracked_names: set[str],
    filename: str = "<unknown>",
) -> list[dict]:
    """Scans an AST tree for direct .bulk_create, .bulk_update, or .update calls on tracked models."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in ("bulk_create", "bulk_update", "update"):
                root_name = _get_root_name(node.func.value)
                if root_name in tracked_names:
                    violations.append(
                        {
                            "filename": filename,
                            "lineno": node.lineno,
                            "model": root_name,
                            "method": method_name,
                            "code": ast.unparse(node),
                        }
                    )
    return violations


class BulkHistoryASTGuardTest(SimpleTestCase):
    """AST guard asserting that tracked models do not call raw bulk operations without history."""

    def test_scan_codebase_where_production_files_checked_should_find_no_unhandled_bulk_operations_on_tracked_models(
        self,
    ):
        # Arrange: identify apps directory and exclude tests and migrations
        apps_root = Path(__file__).resolve().parent.parent.parent
        violations = []

        # Act: scan all production python files in apps/
        for root, _dirs, files in os.walk(apps_root):
            path_parts = Path(root).parts
            if "tests" in path_parts or "migrations" in path_parts or "audit_migrations" in path_parts:
                continue
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root) / file
                try:
                    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
                except SyntaxError:
                    continue
                file_violations = scan_tree_for_bulk_violations(tree, TRACKED_MODEL_NAMES, str(file_path))
                violations.extend(file_violations)

        # Assert: zero unhandled bulk operations on tracked models
        violation_messages = [
            f"{v['filename']}:{v['lineno']} -> {v['model']}.{v['method']}(): {v['code']}" for v in violations
        ]
        assert not violations, (
            f"Found {len(violations)} unhandled bulk operation(s) on tracked models bypassing audit history:\n"
            + "\n".join(violation_messages)
        )

    def test_scan_tree_for_bulk_violations_where_direct_bulk_create_detected_should_report_violation(self):
        # Arrange: synthetic code snippet with direct bulk_create on tracked model
        code = "AssetVersionEntry.objects.bulk_create(entries)"
        tree = ast.parse(code)

        # Act: scan tree
        violations = scan_tree_for_bulk_violations(tree, TRACKED_MODEL_NAMES, "synthetic.py")

        # Assert: 1 violation reported for AssetVersionEntry.bulk_create
        assert len(violations) == 1
        assert violations[0]["model"] == "AssetVersionEntry"
        assert violations[0]["method"] == "bulk_create"

    def test_scan_tree_for_bulk_violations_where_direct_bulk_update_detected_should_report_violation(self):
        # Arrange: synthetic code snippet with direct bulk_update on tracked model
        code = "PublisherMemberInvitation.objects.bulk_update(invitations, ['status'])"
        tree = ast.parse(code)

        # Act: scan tree
        violations = scan_tree_for_bulk_violations(tree, TRACKED_MODEL_NAMES, "synthetic.py")

        # Assert: 1 violation reported for PublisherMemberInvitation.bulk_update
        assert len(violations) == 1
        assert violations[0]["model"] == "PublisherMemberInvitation"
        assert violations[0]["method"] == "bulk_update"

    def test_scan_tree_for_bulk_violations_where_direct_queryset_update_detected_should_report_violation(self):
        # Arrange: synthetic code snippet with chained queryset.update on tracked model
        code = "AssetVersion.objects.filter(asset=asset, asset_language__isnull=True).update(asset_language=source)"
        tree = ast.parse(code)

        # Act: scan tree
        violations = scan_tree_for_bulk_violations(tree, TRACKED_MODEL_NAMES, "synthetic.py")

        # Assert: 1 violation reported for AssetVersion.update
        assert len(violations) == 1
        assert violations[0]["model"] == "AssetVersion"
        assert violations[0]["method"] == "update"
