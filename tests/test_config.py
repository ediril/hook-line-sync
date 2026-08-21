import json
import stat

import pytest

from hls.config import (
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    ServerConfiguration,
)


def test_configuration_round_trip_does_not_persist_secrets(tmp_path) -> None:
    path = tmp_path / ".hls" / "configs.json"
    store = ConfigurationStore(path)
    configuration = ApplicationConfiguration(
        servers={
            "prod": ServerConfiguration(
                host="ftp.example.com",
                username_env="PROD_FTPS_USERNAME",
                password_env="PROD_FTPS_PASSWORD",
            )
        }
    )

    store.save(configuration)

    assert store.load() == configuration
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == 2
    assert "default" not in document
    assert "username" not in document["servers"]["prod"]
    assert "password" not in document["servers"]["prod"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("port", [0, 65536, True, "21"])
def test_server_rejects_invalid_ports(port) -> None:
    with pytest.raises(ConfigurationError, match="port"):
        ServerConfiguration(host="ftp.example.com", port=port)


def test_store_rejects_an_unknown_schema_version(tmp_path) -> None:
    path = tmp_path / "configs.json"
    path.write_text('{"version": 1, "default": null, "servers": {}}')

    with pytest.raises(ConfigurationError, match="unsupported configuration version"):
        ConfigurationStore(path).load()
