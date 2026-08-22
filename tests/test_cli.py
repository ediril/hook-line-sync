import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore
from hls.exclusions import ExclusionSpec
from hls.snapshot import TreeEntry, TreeSnapshot, snapshot_local


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
    version_status, version_stdout, version_stderr = invoke(["v"], store)

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
    assert __version__ == "0.8.22.7"

    help_output = invoke(["help"], store)[1]
    assert "compare (cmp)       preview file changes without modifying anything" in (
        help_output
    )
    assert "push                upload local changes to the remote project" in (
        help_output
    )
    pull_help = (
        "pull                replace changed local files from the remote project"
    )
    assert pull_help in help_output
    assert "usage: hls compare" in invoke(["help", "comp"], store)[1]

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
    with pytest.raises(SystemExit):
        run(["co"], store=store)


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


def test_map_and_ordered_exclusion_commands_persist_reinclusion(
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
    ignored = workspace / "node_modules"
    ignored.mkdir()
    (ignored / "drop.js").write_text("drop", encoding="utf-8")
    (ignored / "keep.js").write_text("keep", encoding="utf-8")

    status, stdout, stderr = invoke(["m", "prod"], store)
    exclude_result = invoke(
        ["exc", ".git/, node_modules/,*.log,**/.cache/"], store
    )
    include_result = invoke(["inc", "node_modules/keep.js"], store)

    assert status == 0 and stderr == ""
    assert stdout == f"Mapped '{workspace}' to 'prod:/public_html'.\n"
    assert exclude_result == (
        0,
        "Excluded for project 'prod': .git/, node_modules/, *.log, **/.cache/.\n",
        "",
    )
    assert include_result == (
        0,
        "Included for project 'prod': node_modules/keep.js.\n",
        "",
    )
    project = store.load().projects["prod"]
    assert project.local_root == str(workspace)
    assert project.exclusions == (
        ".git/",
        "node_modules/",
        "*.log",
        "**/.cache/",
        "!node_modules/keep.js",
    )
    exclusions = ExclusionSpec(project.exclusions)
    assert exclusions.excludes(".git", is_directory=True)
    assert exclusions.excludes("node_modules/package/index.js")
    assert not exclusions.excludes("node_modules/keep.js")
    assert exclusions.excludes("src/debug.log")
    assert not exclusions.excludes("src/main.py")
    snapshot = snapshot_local(workspace, exclusions)
    assert [entry.path for entry in snapshot.entries] == ["node_modules/keep.js"]
    list_stdout = invoke(["list"], store)[1]
    assert "* prod\n" in list_stdout
    assert f"  Local root: {workspace}\n" in list_stdout
    assert (
        "  Rules: exclude .git/, exclude node_modules/, exclude *.log, "
        "exclude **/.cache/, include node_modules/keep.js\n"
    ) in list_stdout
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
    assert invoke(["map", "prod"], store)[0] == 0
    assert invoke(["exclude", "node_modules/,*.log"], store)[0] == 0

    transports = []
    operations = []

    class FakeTransport:
        def __init__(self, project) -> None:
            transports.append(project)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(self, exclusions, selector=None, *, include_excluded=False):
            assert exclusions.patterns == ("node_modules/", "*.log")
            snapshot = TreeSnapshot(
                (
                    TreeEntry(
                        "deployed.html",
                        "file",
                        size=8,
                        modified_ns=1_700_000_000_000_000_000,
                        timestamp_precision_ns=1_000_000_000,
                    ),
                )
            )
            if selector is None or selector.matches("deployed.html"):
                return snapshot
            return TreeSnapshot()

        def make_directory(self, path):
            operations.append(("mkdir", path))

        def upload_file(
            self,
            source,
            path,
            *,
            size,
            modified_ns,
            replace,
        ):
            operations.append(("upload", path, source.read(), size, replace))

        def download_file(self, path, destination):
            operations.append(("download", path))
            destination.write(b"remote")

        def delete_path(self, path, *, is_directory):
            operations.append(("delete", path, is_directory))

    monkeypatch.setattr("hls.cli.ExplicitFTPSTransport", FakeTransport)
    monkeypatch.chdir(source)

    assert invoke(["connect"], store) == (
        0,
        "Verified secure connectivity to project 'prod'.\n",
        "",
    )
    local_listing = (
        0,
        "Local tree for project 'prod':\n"
        "  file      README.md\n"
        "  symlink   linked\n"
        "  directory src/\n"
        "  file      src/main.py\n",
        "",
    )
    remote_listing = (
        0,
        "Remote tree for project 'prod':\n"
        "  file      deployed.html\n",
        "",
    )
    assert invoke(["list", "local"], store) == local_listing
    assert invoke(["lsl"], store) == local_listing
    assert invoke(["list", "remote"], store) == remote_listing
    assert invoke(["lsr"], store) == remote_listing
    push_comparison = invoke(["compare"], store)
    push_progress = (
        "Comparing project 'prod'...\n"
        "Connecting securely over FTPS...\n"
        "Scanning local files...\n"
        "Reading remote files over FTPS...\n"
        "Building push plan...\n"
    )
    assert push_comparison[0] == 0 and push_comparison[2] == push_progress
    assert "Local -> Remote for project 'prod':\n" in push_comparison[1]
    assert "+  README.md\n" in push_comparison[1]
    assert "-  deployed.html\n" in push_comparison[1]
    assert "!  linked\n" in push_comparison[1]
    assert "·  node_modules/package.js\n" in push_comparison[1]
    assert "·  src/debug.log\n" in push_comparison[1]
    assert invoke(["cmp"], store) == push_comparison

    selected_comparison = invoke(["compare", "main.py"], store)
    assert selected_comparison[0] == 0
    assert selected_comparison[2] == push_progress
    assert "src/main.py" in selected_comparison[1]
    assert "README.md" not in selected_comparison[1]
    assert "deployed.html" not in selected_comparison[1]

    monkeypatch.chdir(workspace)
    expanded_comparison = invoke(
        ["compare", "README.md", "src", "src/main.py"], store
    )
    assert expanded_comparison[0] == 0
    assert "+  README.md\n" in expanded_comparison[1]
    assert "+  src/main.py\n" in expanded_comparison[1]
    assert "+  src\n" not in expanded_comparison[1]
    monkeypatch.chdir(source)

    colored_comparison = invoke(["compare", "*", "--color", "always"], store)
    assert "\033[32m+  src/main.py\033[0m" in colored_comparison[1]
    assert "\033[90m·  src/debug.log\033[0m" in colored_comparison[1]

    pull_comparison = invoke(["compare", "--pull", "-p"], store)
    assert pull_comparison[0] == 0
    assert pull_comparison[2].endswith("Building pull plan...\n")
    assert "Remote -> Local for project 'prod':\n" in pull_comparison[1]
    assert "+  deployed.html\n" in pull_comparison[1]
    assert "-  README.md\n" in pull_comparison[1]

    push_result = invoke(["push", "main.py"], store)
    assert push_result[0] == 0
    assert push_result[2].startswith("Preparing push for project 'prod'...\n")
    assert push_result[2].endswith("Executing push plan...\n")
    assert "Push completed for project 'prod': 1 change(s)." in push_result[1]
    assert operations == [
        ("mkdir", "src"),
        ("upload", "src/main.py", b"print('hello')", 14, False),
    ]
    monkeypatch.chdir(workspace)
    pull_result = invoke(["pull", "deployed.html"], store)
    assert pull_result[0] == 0
    assert pull_result[2].startswith("Preparing pull for project 'prod'...\n")
    assert pull_result[2].endswith("Executing pull plan...\n")
    assert "Pull completed for project 'prod': 0 change(s)." in pull_result[1]
    assert "skip           remote-only" in pull_result[1]
    assert len(transports) == 11


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
