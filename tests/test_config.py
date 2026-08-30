import json
import stat
from pathlib import Path

import pytest

from hlsync.config import (
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    ProfileConfiguration,
    canonical_local_root,
)
from hlsync.rules import SyncRule


def test_configuration_round_trip_persists_mapping_without_secrets(tmp_path) -> None:
    path = tmp_path / ".hlsync" / "configs.json"
    local_root = tmp_path / "site"
    local_root.mkdir()
    configuration = ApplicationConfiguration(
        profiles={
            "prod": ProfileConfiguration(
                host="ftp.example.com",
                remote_root="/public_html",
                local_root=canonical_local_root(local_root),
                rules=(
                    SyncRule(1, "exclude", "node_modules/**"),
                    SyncRule(2, "exclude", "*.log"),
                ),
            )
        }
    )
    store = ConfigurationStore(path)

    assert ConfigurationStore().path == Path.home() / ".hlsync" / "configs.json"

    store.save(configuration)

    assert store.load() == configuration
    document = json.loads(path.read_text(encoding="utf-8"))
    profile = document["profiles"]["prod"]
    assert document["version"] == 9
    assert profile["local_root"] == str(local_root)
    assert profile["rules"] == [
        {"id": 1, "action": "exclude", "pattern": "node_modules/**"},
        {"id": 2, "action": "exclude", "pattern": "*.log"},
    ]
    assert "next_rule_id" not in profile
    assert "username" not in profile and "password" not in profile
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("port", [0, 65536, True, "21"])
def test_profile_rejects_invalid_ports(port) -> None:
    with pytest.raises(ConfigurationError, match="port"):
        ProfileConfiguration(
            host="ftp.example.com", remote_root="/public_html", port=port
        )


def test_store_rejects_old_configuration_schemas(tmp_path) -> None:
    path = tmp_path / "configs.json"
    path.write_text('{"version": 8, "profiles": {}}')

    message = (
        r"config version mismatch \(found 8, expected 9\); configuration "
        r"schema changed—recreate config"
    )
    with pytest.raises(ConfigurationError, match=message):
        ConfigurationStore(path).load()

    path.write_text('{"version": 9, "projects": {}}')
    with pytest.raises(
        ConfigurationError,
        match="configuration has unknown or missing fields",
    ):
        ConfigurationStore(path).load()
