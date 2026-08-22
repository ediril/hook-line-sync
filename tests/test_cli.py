import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore
from hls.exclusions import ExclusionSpec
from hls.snapshot import TreeEntry, TreeSnapshot


def invoke(arguments, store):
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = run(arguments, store=store, stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def test_project_lifecycle_uses_production_credentials_and_version(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    monkeypatch.chdir(tmp_path)

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
    project = store.load().projects["client-site"]
    assert project.host == "ftp.example.com"
    assert project.remote_root == "/public_html/site"
    assert project.local_root is None
    assert project.username_env == "PROD_FTPS_USERNAME"
    assert project.password_env == "PROD_FTPS_PASSWORD"
    assert __version__ == "0.8.21.11"

    list_status, list_stdout, list_stderr = invoke(["list"], store)
    assert (list_status, list_stderr) == (0, "")
    assert "- client-site\n" in list_stdout
    assert "  Local root: not mapped\n" in list_stdout
    assert invoke(["ls"], store)[1] == list_stdout

    assert invoke(["remove", "client-site"], store) == (
        0,
        "Removed project 'client-site'.\n",
        "",
    )
    assert invoke(["list"], store)[1] == "No projects configured.\n"


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

    duplicate_status, _, duplicate_error = invoke(arguments, store)
    missing_status, _, missing_error = invoke(["connect", "missing"], store)

    assert duplicate_status == 1 and "already exists" in duplicate_error
    assert missing_status == 1 and "does not exist" in missing_error
    with pytest.raises(SystemExit):
        run(["add", "unsafe", "--host", "ftp.example.com"], store=store)


def test_add_supports_explicit_protocol_port_and_environment_names(tmp_path) -> None:
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
    assert (project.type, project.port, project.username_env, project.password_env) == (
        "ftps",
        2121,
        "SHARED_USER",
        "STAGING_SECRET",
    )


def test_map_uses_current_directory_and_compiles_comma_separated_exclusions(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
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

    status, stdout, stderr = invoke(
        ["map", "prod", "--exclude", ".git/, node_modules/,*.log,**/.cache/"],
        store,
    )

    assert status == 0 and stderr == ""
    assert stdout.startswith(f"Mapped '{workspace}' to 'prod:/public_html'.")
    project = store.load().projects["prod"]
    assert project.local_root == str(workspace)
    assert project.exclusions == ("**/.cache/", "*.log", ".git/", "node_modules/")
    exclusions = ExclusionSpec(project.exclusions)
    assert exclusions.excludes(".git", is_directory=True)
    assert exclusions.excludes("node_modules/package/index.js")
    assert exclusions.excludes("src/debug.log")
    assert not exclusions.excludes("src/main.py")
    list_stdout = invoke(["list"], store)[1]
    assert "* prod\n" in list_stdout
    assert f"  Local root: {workspace}\n" in list_stdout
    assert "  Excludes: **/.cache/, *.log, .git/, node_modules/\n" in list_stdout
    assert "project mapped to the current directory" not in list_stdout


def test_current_project_inference_drives_connect_and_tree_listings(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    source = workspace / "src"
    ignored = workspace / "node_modules"
    outside = tmp_path / "outside"
    source.mkdir(parents=True)
    ignored.mkdir()
    outside.mkdir()
    (workspace / "README.md").write_text("read me", encoding="utf-8")
    (source / "main.py").write_text("print('hello')", encoding="utf-8")
    (source / "debug.log").write_text("ignored", encoding="utf-8")
    (ignored / "package.js").write_text("ignored", encoding="utf-8")
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    (workspace / "linked").symlink_to(outside, target_is_directory=True)
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
    assert invoke(
        ["map", "prod", "--exclude", "node_modules/,*.log"], store
    )[0] == 0

    transports = []

    class FakeTransport:
        def __init__(self, project) -> None:
            transports.append(project)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(self, exclusions):
            assert exclusions.patterns == ("*.log", "node_modules/")
            return TreeSnapshot((TreeEntry("deployed.html", "file"),))

    monkeypatch.setattr("hls.cli.ExplicitFTPSTransport", FakeTransport)
    monkeypatch.chdir(source)

    assert invoke(["connect"], store) == (
        0,
        "Connected securely to project 'prod'.\n",
        "",
    )
    assert invoke(["list", "local"], store) == (
        0,
        "Local tree for project 'prod':\n"
        "  file      README.md\n"
        "  symlink   linked\n"
        "  directory src/\n"
        "  file      src/main.py\n",
        "",
    )
    assert invoke(["list", "remote"], store) == (
        0,
        "Remote tree for project 'prod':\n"
        "  file      deployed.html\n",
        "",
    )
    assert len(transports) == 2


def test_map_rejects_existing_and_overlapping_local_roots(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    root = tmp_path / "root"
    child = root / "child"
    separate = tmp_path / "separate"
    child.mkdir(parents=True)
    separate.mkdir()
    for name in ("prod", "staging"):
        invoke(
            [
                "add",
                name,
                "--host",
                "ftp.example.com",
                "--remote-root",
                f"/{name}",
            ],
            store,
        )

    monkeypatch.chdir(root)
    assert invoke(["map", "prod"], store)[0] == 0
    monkeypatch.chdir(child)
    overlap_status, _, overlap_error = invoke(["map", "staging"], store)
    monkeypatch.chdir(separate)
    existing_status, _, existing_error = invoke(["map", "prod"], store)

    assert overlap_status == 1
    assert "overlaps project 'prod'" in overlap_error
    assert str(root) in overlap_error and str(child) in overlap_error
    assert existing_status == 1
    assert "already mapped" in existing_error
    assert store.load().projects["staging"].local_root is None
