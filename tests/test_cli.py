import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore
from hls.context import DirectoryContexts, DirectoryContextStore


def invoke(arguments, store):
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = run(
        arguments,
        store=store,
        context_store=DirectoryContextStore(store.path.with_name("contexts.json")),
        stdout=stdout,
        stderr=stderr,
    )
    return status, stdout.getvalue(), stderr.getvalue()


def test_project_lifecycle_uses_production_credentials_and_version(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    add_status, add_stdout, add_stderr = invoke(
        [
            "add",
            "client-site",
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
        "Added FTPS project 'client-site'.\n",
        "",
    )
    assert (version_status, version_stdout, version_stderr) == (
        0,
        f"{__version__}\n",
        "",
    )
    configuration = store.load()
    project = configuration.projects["client-site"]
    assert project.host == "ftp.example.com"
    assert project.remote_root == "/public_html/site"
    assert project.type == "ftps"
    assert project.port == 21
    assert project.username_env == "PROD_FTPS_USERNAME"
    assert project.password_env == "PROD_FTPS_PASSWORD"
    assert __version__ == "0.8.21.9"

    context_store = DirectoryContextStore(store.path.with_name("contexts.json"))
    contexts = DirectoryContexts()
    contexts.bind(tmp_path.resolve(), "client-site")
    context_store.save(contexts)
    monkeypatch.chdir(tmp_path)
    list_status, list_stdout, list_stderr = invoke(["list"], store)
    alias_status, alias_stdout, alias_stderr = invoke(["ls"], store)
    assert (list_status, list_stderr) == (0, "")
    assert (alias_status, alias_stderr) == (0, "")
    assert alias_stdout == list_stdout
    assert "* client-site\n" in list_stdout
    assert "  FTPS: ftp.example.com:21\n" in list_stdout
    assert "  Remote root: /public_html/site\n" in list_stdout
    assert "  Mappings: none\n" in list_stdout
    assert f"* active project from '{tmp_path.resolve()}'\n" in list_stdout
    remove_status, remove_stdout, remove_stderr = invoke(
        ["remove", "client-site"], store
    )
    assert (remove_status, remove_stdout, remove_stderr) == (
        0,
        "Removed project 'client-site'.\n",
        "",
    )
    assert store.load().projects == {}
    assert context_store.load().bindings == {}
    assert invoke(["list"], store)[1] == "No projects configured.\n"
    missing_status, _, missing_error = invoke(["remove", "client-site"], store)
    assert missing_status == 1
    assert "does not exist" in missing_error


def test_cli_refuses_invalid_project_mutations(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    arguments = [
        "add",
        "prod",
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
    context_status, _, context_error = invoke(["connect"], store)
    assert context_status == 1
    assert "no directory context" in context_error
    with pytest.raises(SystemExit):
        run(["add", "unsafe", "--host", "ftp.example.com"], store=store)


def test_add_supports_custom_port_and_environment_names(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")

    status, _, _ = invoke(
        [
            "add",
            "staging",
            "--host",
            "staging.example.com",
            "--remote-root",
            "/clients/staging",
            "--protocol",
            "ftps",
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
    assert (
        project.type,
        project.port,
        project.username_env,
        project.password_env,
    ) == (
        "ftps",
        2121,
        "SHARED_USER",
        "STAGING_SECRET",
    )


def test_use_is_directory_scoped_and_map_persists_an_absolute_local_path(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    local_folder = workspace / "site"
    unrelated = tmp_path / "unrelated"
    local_folder.mkdir(parents=True)
    unrelated.mkdir()
    invoke(
        [
            "add",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
        ],
        store,
    )
    monkeypatch.chdir(workspace)
    use_status, _, use_error = invoke(["use", "prod"], store)
    monkeypatch.chdir(local_folder)

    status, stdout, stderr = invoke(["map", "."], store)

    assert use_status == 0 and use_error == ""
    assert status == 0
    assert stdout == f"Mapped '{local_folder}' to 'prod:/public_html/site'.\n"
    assert stderr == ""
    mapping = store.load().projects["prod"].mappings[0]
    assert mapping.local == str(local_folder)
    assert mapping.remote == "site"
    list_status, list_stdout, _ = invoke(["list", "projects"], store)
    assert list_status == 0
    assert f"    {local_folder} -> /public_html/site\n" in list_stdout
    show_status, show_stdout, _ = invoke(["use"], store)
    assert show_status == 0
    assert show_stdout == f"Using project 'prod' from '{workspace}'.\n"

    monkeypatch.chdir(unrelated)
    unrelated_status, _, unrelated_error = invoke(["map", "."], store)
    assert unrelated_status == 1
    assert "no directory context" in unrelated_error

    monkeypatch.chdir(workspace)
    clear_status, _, clear_error = invoke(["use", "--clear"], store)
    assert clear_status == 0 and clear_error == ""


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
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/project",
        ],
        store,
    )
    assert invoke(["map", str(site), "site", "--project", "prod"], store)[0] == 0

    local_status, _, local_error = invoke(
        ["map", str(child), "other", "--project", "prod"], store
    )
    remote_status, _, remote_error = invoke(
        ["map", str(separate), "site/assets", "--project", "prod"], store
    )
    absolute_status, _, absolute_error = invoke(
        ["map", str(outside), "/another-project", "--project", "prod"], store
    )

    assert local_status == 1
    assert "local path" in local_error and "overlaps" in local_error
    assert remote_status == 1
    assert "remote path" in remote_error and "overlaps" in remote_error
    assert absolute_status == 1
    assert "must be relative" in absolute_error
    assert len(store.load().projects["prod"].mappings) == 1
