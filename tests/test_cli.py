import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore


def invoke(arguments, store):
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = run(arguments, store=store, stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def test_project_lifecycle_uses_derived_credentials_and_version(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    add_status, add_stdout, add_stderr = invoke(
        [
            "add",
            "prod",
            "ftps",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html/site",
        ],
        store,
    )
    version_status, version_stdout, version_stderr = invoke(["version"], store)

    assert (add_status, add_stdout, add_stderr) == (
        0,
        "Added FTPS project 'prod'.\n",
        "",
    )
    assert (version_status, version_stdout, version_stderr) == (
        0,
        f"{__version__}\n",
        "",
    )
    configuration = store.load()
    project = configuration.projects["prod"]
    assert project.host == "ftp.example.com"
    assert project.remote_root == "/public_html/site"
    assert project.port == 21
    assert project.username_env == "PROD_FTPS_USERNAME"
    assert project.password_env == "PROD_FTPS_PASSWORD"
    assert __version__ == "0.8.21.4"

    remove_status, remove_stdout, remove_stderr = invoke(["remove", "prod"], store)
    assert (remove_status, remove_stdout, remove_stderr) == (
        0,
        "Removed project 'prod'.\n",
        "",
    )
    assert store.load().projects == {}
    missing_status, _, missing_error = invoke(["remove", "prod"], store)
    assert missing_status == 1
    assert "does not exist" in missing_error


def test_cli_refuses_invalid_project_mutations(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    arguments = [
        "add",
        "prod",
        "ftps",
        "--host",
        "ftp.example.com",
        "--remote-root",
        "/public_html/site",
    ]
    assert invoke(arguments, store)[0] == 0

    duplicate_status, duplicate_stdout, duplicate_stderr = invoke(arguments, store)
    missing_status, missing_stdout, missing_stderr = invoke(
        ["connect", "missing"], store
    )

    assert (duplicate_status, duplicate_stdout) == (1, "")
    assert "already exists" in duplicate_stderr
    assert (missing_status, missing_stdout) == (1, "")
    assert "does not exist" in missing_stderr
    with pytest.raises(SystemExit):
        run(["connect"], store=store)
    with pytest.raises(SystemExit):
        run(["add", "unsafe", "ftps", "--host", "ftp.example.com"], store=store)


def test_add_supports_custom_port_and_environment_names(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    status, _, _ = invoke(
        [
            "add",
            "staging",
            "ftps",
            "--host",
            "staging.example.com",
            "--remote-root",
            "/clients/staging",
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
    project = store.load().projects["staging"]
    assert (project.port, project.username_env, project.password_env) == (
        2121,
        "SHARED_USER",
        "STAGING_SECRET",
    )


def test_map_uses_an_explicit_project_and_canonicalizes_the_current_folder(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    local_folder = tmp_path / "site"
    local_folder.mkdir()
    invoke(
        [
            "add",
            "prod",
            "ftps",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
        ],
        store,
    )
    monkeypatch.chdir(local_folder)

    status, stdout, stderr = invoke(["map", "prod", "/public_html/"], store)

    assert status == 0
    assert stdout == f"Mapped '{local_folder}' to 'prod:/public_html'.\n"
    assert stderr == ""
    assert store.load().projects["prod"].mappings[0].local == str(local_folder)


def test_map_rejects_local_and_remote_overlaps(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    site = tmp_path / "site"
    child = site / "assets"
    separate = tmp_path / "separate"
    child.mkdir(parents=True)
    separate.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    invoke(
        [
            "add",
            "prod",
            "ftps",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/project",
        ],
        store,
    )
    assert invoke(["map", "prod", "/project/site", str(site)], store)[0] == 0

    local_status, _, local_error = invoke(
        ["map", "prod", "/project/other", str(child)], store
    )
    remote_status, _, remote_error = invoke(
        ["map", "prod", "/project/site/assets", str(separate)], store
    )
    root_status, _, root_error = invoke(
        ["map", "prod", "/another-project", str(outside)], store
    )

    assert local_status == 1
    assert "local path" in local_error and "overlaps" in local_error
    assert remote_status == 1
    assert "remote path" in remote_error and "overlaps" in remote_error
    assert root_status == 1
    assert "outside project root" in root_error
    assert len(store.load().projects["prod"].mappings) == 1
