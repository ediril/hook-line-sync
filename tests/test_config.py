import json
import stat

import pytest

from hls.config import (
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    ProjectConfiguration,
    canonical_local_root,
)
from hls.rules import SyncRule


def test_configuration_round_trip_persists_mapping_without_secrets(tmp_path) -> None:
    path = tmp_path / ".hls" / "configs.json"
    local_root = tmp_path / "site"
    local_root.mkdir()
    configuration = ApplicationConfiguration(
        projects={
            "prod": ProjectConfiguration(
                host="ftp.example.com",
                remote_root="/public_html",
                local_root=canonical_local_root(local_root),
                rules=(
                    SyncRule(1, "exclude", "node_modules/**"),
                    SyncRule(2, "exclude", "*.log"),
                ),
                next_rule_id=3,
            )
        }
    )
    store = ConfigurationStore(path)

    store.save(configuration)

    assert store.load() == configuration
    document = json.loads(path.read_text(encoding="utf-8"))
    project = document["projects"]["prod"]
    assert document["version"] == 7
    assert project["local_root"] == str(local_root)
    assert project["rules"] == [
        {"id": 1, "action": "exclude", "pattern": "node_modules/**"},
        {"id": 2, "action": "exclude", "pattern": "*.log"},
    ]
    assert project["next_rule_id"] == 3
    assert "username" not in project and "password" not in project
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("port", [0, 65536, True, "21"])
def test_project_rejects_invalid_ports(port) -> None:
    with pytest.raises(ConfigurationError, match="port"):
        ProjectConfiguration(
            host="ftp.example.com", remote_root="/public_html", port=port
        )


def test_store_rejects_an_unknown_schema_version(tmp_path) -> None:
    path = tmp_path / "configs.json"
    path.write_text('{"version": 6, "projects": {}}')

    with pytest.raises(ConfigurationError, match="unsupported configuration version"):
        ConfigurationStore(path).load()
