import json
import stat

import pytest

from hls.config import (
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    DirectoryMapping,
    ProjectConfiguration,
)


def test_configuration_round_trip_does_not_persist_secrets(tmp_path) -> None:
    path = tmp_path / ".hls" / "configs.json"
    local_folder = tmp_path / "site"
    local_folder.mkdir()
    store = ConfigurationStore(path)
    configuration = ApplicationConfiguration(
        projects={
            "prod": ProjectConfiguration(
                host="ftp.example.com",
                remote_root="/public_html",
                username_env="PROD_FTPS_USERNAME",
                password_env="PROD_FTPS_PASSWORD",
                mappings=(DirectoryMapping.create(local_folder, "/public_html"),),
            )
        }
    )

    store.save(configuration)

    assert store.load() == configuration
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == 4
    assert "default" not in document
    assert "servers" not in document
    assert "username" not in document["projects"]["prod"]
    assert "password" not in document["projects"]["prod"]
    assert document["projects"]["prod"]["remote_root"] == "/public_html"
    assert document["projects"]["prod"]["mappings"] == [
        {"local": str(local_folder), "remote": "/public_html"}
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("port", [0, 65536, True, "21"])
def test_project_rejects_invalid_ports(port) -> None:
    with pytest.raises(ConfigurationError, match="port"):
        ProjectConfiguration(
            host="ftp.example.com", remote_root="/public_html", port=port
        )


def test_store_rejects_an_unknown_schema_version(tmp_path) -> None:
    path = tmp_path / "configs.json"
    path.write_text('{"version": 3, "servers": {}}')

    with pytest.raises(ConfigurationError, match="unsupported configuration version"):
        ConfigurationStore(path).load()
