"""Home Assistant runtime fixtures for integration-level tests."""

from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Create an isolated HA config directory containing this integration."""
    repository_root = Path(__file__).parents[2]
    copytree(
        repository_root / "custom_components",
        tmp_path / "custom_components",
    )
    return str(tmp_path)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations) -> None:
    """Allow Home Assistant to load the copied custom integration."""
