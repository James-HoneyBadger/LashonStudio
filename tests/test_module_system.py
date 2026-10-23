"""Tests for the config-driven module system."""

import pytest

from parsercraft.config import LanguageConfig
from parsercraft.runtime.module_system import (
    ModuleManager,
    ParserCraftModuleNotFoundError,
)


@pytest.fixture
def config():
    return LanguageConfig.from_preset("python_like")


@pytest.fixture
def module_dir(tmp_path):
    (tmp_path / "math.lang").write_text(
        "export function add(a, b)\n"
        "export const PI\n",
        encoding="utf-8",
    )
    (tmp_path / "app.lang").write_text(
        "import math\n"
        "import {add, PI} from math\n"
        "export function main()\n",
        encoding="utf-8",
    )
    (tmp_path / "cycle_a.lang").write_text("import cycle_b\n", encoding="utf-8")
    (tmp_path / "cycle_b.lang").write_text("import cycle_a\n", encoding="utf-8")
    return tmp_path


def test_load_module_parses_exports(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    module = manager.load_module("math")
    assert module.name == "math"
    assert set(module.exports) == {"add", "PI"}
    assert module.exports["add"].kind == "function"


def test_module_is_cached(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    first = manager.load_module("math")
    second = manager.load_module("math")
    assert first is second


def test_imports_are_parsed(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    module = manager.load_module("app")
    assert [dep.module_name for dep in module.dependencies] == ["math", "math"]
    assert module.dependencies[1].selected == ["add", "PI"]


def test_resolve_dependencies(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    assert manager.resolve_dependencies("app") == ["math", "math"]


def test_circular_dependencies_are_detected(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    manager.resolve_dependencies("cycle_a")
    manager.resolve_dependencies("cycle_b")
    cycles = manager.detect_circular_dependencies()
    assert cycles


def test_missing_module_raises(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    with pytest.raises(ParserCraftModuleNotFoundError):
        manager.load_module("does_not_exist")


def test_get_module_info(config, module_dir):
    manager = ModuleManager(config, search_paths=[str(module_dir)])
    info = manager.get_module_info("math")
    assert info["name"] == "math"
    assert set(info["exports"]) == {"add", "PI"}
