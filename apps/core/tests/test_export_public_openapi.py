import json

from django.core.management import call_command


class TestExportPublicOpenapi:
    def test_export_public_openapi_whenOutFlagGiven_shouldWriteValidJsonAtPath(self, tmp_path):
        # Arrange
        out = tmp_path / "spec.json"

        # Act
        call_command("export_public_openapi", out=str(out))

        # Assert
        assert out.exists()
        data = json.loads(out.read_text())
        assert isinstance(data, dict)

    def test_export_public_openapi_whenOutFlagGiven_shouldIncludeDevelopersApiPaths(self, tmp_path):
        # Arrange
        out = tmp_path / "spec.json"

        # Act
        call_command("export_public_openapi", out=str(out))

        # Assert
        data = json.loads(out.read_text())
        assert "paths" in data
        assert len(data["paths"]) > 0

    def test_export_public_openapi_whenOutDirMissing_shouldCreateParentDirectories(self, tmp_path):
        # Arrange
        out = tmp_path / "nested" / "deep" / "spec.json"

        # Act
        call_command("export_public_openapi", out=str(out))

        # Assert
        assert out.exists()
