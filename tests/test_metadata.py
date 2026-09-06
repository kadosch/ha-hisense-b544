"""Repository metadata and translation consistency tests."""

import ast
import json
import tomllib
from pathlib import Path

from custom_components.hisense_b544.const import DOMAIN

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / DOMAIN


def load_json(path: Path) -> dict:
    """Load one repository JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_and_hacs_metadata_are_publishable():
    """Require release metadata accepted by Home Assistant and HACS."""
    manifest = load_json(INTEGRATION / "manifest.json")
    hacs = load_json(ROOT / "hacs.json")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == ["modbus"]
    assert manifest["integration_type"] == "hub"
    assert manifest["codeowners"] == ["@kadosch"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert "OWNER" not in manifest["documentation"]
    assert manifest["issue_tracker"].endswith("/issues")
    assert manifest["version"] == project["project"]["version"]
    assert f"## {manifest['version']} - " in changelog
    assert hacs == {"name": "Hisense B544", "homeassistant": "2026.9.0"}


def test_translations_cover_every_config_flow_field():
    """Require complete bus and B544 subentry translations in every language."""
    required_fields = {
        "serial": {"device", "baudrate", "name"},
        "tcp": {"host", "port", "name"},
    }
    device_fields = {"scan_interval", "unit_id", "name", "model"}

    for path in (
        INTEGRATION / "strings.json",
        INTEGRATION / "translations" / "en.json",
        INTEGRATION / "translations" / "es.json",
    ):
        document = load_json(path)
        for step, fields in required_fields.items():
            assert set(document["config"]["step"][step]["data"]) == fields
        for step in ("user", "reconfigure"):
            assert set(document["config_subentries"]["b544"]["step"][step]["data"]) == (
                device_fields
            )


def test_all_distributed_python_definitions_have_docstrings():
    """Require docstrings even for private methods not covered by pydocstyle."""
    missing = []
    for path in sorted(INTEGRATION.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        missing.extend(
            f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and ast.get_docstring(node) is None
        )

    assert missing == []
