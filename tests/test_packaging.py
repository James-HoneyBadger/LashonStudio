"""Tests for package versioning, registry, and generated documentation."""

import json

import pytest

from parsercraft.config import LanguageConfig
from parsercraft.packaging.documentation_generator import DocumentationGenerator
from parsercraft.packaging.package_registry import (
    Package,
    PackageRegistry,
    Version,
    VersionConstraint,
)
from parsercraft.packaging.vscode_integration import generate_vscode_extension


class TestVersion:
    def test_release_ordering(self):
        assert Version.parse("1.2.3") < Version.parse("1.10.0")
        assert Version.parse("2.0.0") > Version.parse("1.99.99")

    def test_prerelease_precedes_release(self):
        assert Version.parse("1.2.3-rc.1") < Version.parse("1.2.3")
        assert Version.parse("1.2.3-rc.1") < Version.parse("1.2.3-rc.2")

    def test_equality_includes_prerelease(self):
        assert Version.parse("1.2.3-rc.1") != Version.parse("1.2.3")
        assert Version.parse("1.2.3+build.1") == Version.parse("1.2.3")

    def test_versions_are_hashable(self):
        assert len({Version.parse("1.0.0"), Version.parse("1.0.0")}) == 1

    def test_invalid_version_raises(self):
        with pytest.raises(ValueError):
            Version.parse("not-a-version")


class TestVersionConstraint:
    @pytest.mark.parametrize("constraint,version,expected", [
        ("^1.2.0", "1.5.0", True),
        ("^1.2.0", "2.0.0", False),
        ("~1.2.0", "1.2.9", True),
        ("~1.2.0", "1.3.0", False),
        (">=1.2.0", "1.2.0", True),
        ("<2.0.0", "1.9.9", True),
        ("==1.2.3", "1.2.3", True),
    ])
    def test_satisfies(self, constraint, version, expected):
        parsed = VersionConstraint.parse(constraint)
        assert parsed.satisfies(Version.parse(version)) is expected


class TestPackageRegistry:
    def test_resolve_picks_highest_satisfying_version(self):
        registry = PackageRegistry()
        registry.register_package(Package("math", Version.parse("1.0.0")))
        registry.register_package(Package("math", Version.parse("1.4.0")))
        registry.register_package(Package("math", Version.parse("2.0.0")))

        resolved = registry.resolve("math", "^1.0.0")
        assert resolved is not None
        assert str(resolved.version) == "1.4.0"

    def test_resolve_missing_package_returns_none(self):
        assert PackageRegistry().resolve("missing", "^1.0.0") is None

    def test_package_round_trip(self):
        package = Package(
            "math",
            Version.parse("1.2.3"),
            description="Math helpers",
            dependencies={"core": "^1.0.0"},
        )
        restored = Package.from_dict(package.to_dict())
        assert restored.name == package.name
        assert restored.version == package.version
        assert restored.dependencies == package.dependencies


class TestGeneratedAssets:
    @pytest.fixture
    def config(self):
        return LanguageConfig.from_preset("python_like")

    def test_markdown_documentation(self, config):
        markdown = DocumentationGenerator.generate_markdown(config)
        assert config.name in markdown
        assert "# " in markdown

    def test_save_markdown(self, config, tmp_path):
        output = tmp_path / "reference.md"
        DocumentationGenerator.save_markdown(config, str(output))
        assert output.read_text(encoding="utf-8").startswith("#")

    def test_vscode_extension_files(self, config, tmp_path):
        output = tmp_path / "extension"
        generate_vscode_extension(config, str(output))

        package_json = json.loads(
            (output / "package.json").read_text(encoding="utf-8")
        )
        assert package_json["publisher"] == "parsercraft"
        assert (output / "language-configuration.json").exists()
        grammars = list((output / "syntaxes").glob("*.tmLanguage.json"))
        assert grammars
