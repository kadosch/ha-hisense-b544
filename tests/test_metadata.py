"""Repository metadata and translation consistency tests."""

import json
from pathlib import Path

from custom_components.hisense_b544.const import DOMAIN

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / DOMAIN


def load_json(path: Path) -> dict:
    """Load one repository JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_and_hacs_metadata_are_structurally_valid():
    manifest = load_json(INTEGRATION / "manifest.json")
    hacs = load_json(ROOT / "hacs.json")

    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == ["modbus"]
    assert isinstance(manifest["codeowners"], list)
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    assert hacs == {"name": "Hisense B544", "homeassistant": "2026.9.1"}


def test_translations_cover_every_config_flow_field():
    required_fields = {
        "serial": {
            "device",
            "baudrate",
            "scan_interval",
            "unit_id",
            "name",
            "model",
        },
        "tcp": {"host", "port", "scan_interval", "unit_id", "name", "model"},
    }

    for path in (
        INTEGRATION / "strings.json",
        INTEGRATION / "translations" / "en.json",
        INTEGRATION / "translations" / "es.json",
    ):
        document = load_json(path)
        for step, fields in required_fields.items():
            assert set(document["config"]["step"][step]["data"]) == fields
        assert "scan_interval" in document["options"]["step"]["init"]["data"]
