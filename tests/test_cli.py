import io

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore


def invoke(arguments, store):
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = run(arguments, store=store, stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def test_profile_lifecycle_uses_derived_credentials_and_version(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    add_status, add_stdout, add_stderr = invoke(
        ["add", "prod", "ftps", "--host", "ftp.example.com"], store
    )
    set_status, set_stdout, set_stderr = invoke(["set", "prod"], store)
    version_status, version_stdout, version_stderr = invoke(["version"], store)

    assert (add_status, add_stdout, add_stderr) == (
        0,
        "Added FTPS configuration 'prod'.\n",
        "",
    )
    assert (set_status, set_stdout, set_stderr) == (
        0,
        "Default configuration set to 'prod'.\n",
        "",
    )
    assert (version_status, version_stdout, version_stderr) == (
        0,
        f"{__version__}\n",
        "",
    )
    configuration = store.load()
    server = configuration.servers["prod"]
    assert server.host == "ftp.example.com"
    assert server.port == 21
    assert server.username_env == "PROD_FTPS_USERNAME"
    assert server.password_env == "PROD_FTPS_PASSWORD"
    assert configuration.default == "prod"
    assert __version__ == "0.8.21.1"


def test_cli_refuses_invalid_profile_mutations(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    arguments = ["add", "prod", "ftps", "--host", "ftp.example.com"]
    assert invoke(arguments, store)[0] == 0

    duplicate_status, duplicate_stdout, duplicate_stderr = invoke(arguments, store)
    missing_status, missing_stdout, missing_stderr = invoke(["set", "missing"], store)

    assert (duplicate_status, duplicate_stdout) == (1, "")
    assert "already exists" in duplicate_stderr
    assert (missing_status, missing_stdout) == (1, "")
    assert "does not exist" in missing_stderr


def test_add_supports_custom_port_and_environment_names(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    status, _, _ = invoke(
        [
            "add",
            "staging",
            "ftps",
            "--host",
            "staging.example.com",
            "--port",
            "2121",
            "--username-env",
            "SHARED_USER",
            "--password-env",
            "STAGING_SECRET",
        ],
        store,
    )

    assert status == 0
    server = store.load().servers["staging"]
    assert (server.port, server.username_env, server.password_env) == (
        2121,
        "SHARED_USER",
        "STAGING_SECRET",
    )
