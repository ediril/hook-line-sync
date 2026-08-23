import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore
from hls.rules import RuleSet, SyncRule
from hls.snapshot import TreeEntry, TreeSnapshot, snapshot_local


def invoke(arguments, store, *, stdin="no\n"):
    input_stream = io.StringIO(stdin)
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = run(
        arguments,
        store=store,
        stdin=input_stream,
        stdout=stdout,
        stderr=stderr,
    )
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
        f"Map current directory '{tmp_path}' to "
        "'client-site:/public_html/site'? [Y/n] "
        "Added FTPS project 'client-site' without a local mapping.\n",
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

    help_output = invoke(["help"], store)[1]
    assert "diff                preview file changes without modifying anything" in (
        help_output
    )
    assert "compare" not in help_output
    assert "list (ls)" not in help_output
    assert "explain" not in help_output
    assert "push                upload local changes to the remote project" in (
        help_output
    )
    pull_help = (
        "pull                replace changed local files from the remote project"
    )
    assert pull_help in help_output
    assert "usage: hls diff" in invoke(["help", "d"], store)[1]
    rules_help = invoke(["help", "rules"], store)[1]
    assert "hls rules [--project PROJECT_NAME]" in rules_help
    assert "hls rules remove RULE_ID [--project PROJECT_NAME]" in rules_help
    assert "[{remove}] [rule_id]" not in rules_help
    list_help = invoke(["help", "list"], store)[1]
    assert "hls list [projects]" in list_help
    assert "hls list local [PROJECT]" in list_help
    assert "hls list remote [PROJECT]" in list_help
    assert "[{projects,local,remote}] [project_name]" not in list_help
    for command in ("exclude", "include"):
        rule_help = invoke(["help", command], store)[1]
        assert f"hls {command} [PATH ...]" in rule_help
        assert f"hls {command} --pattern PATTERN ..." in rule_help

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


def test_add_maps_the_current_directory_after_confirmation(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    result = invoke(
        [
            "add",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
        ],
        store,
        stdin="\n",
    )

    assert result == (
        0,
        f"Map current directory '{workspace}' to 'prod:/public_html'? [Y/n] "
        "Added FTPS project 'prod'.\n"
        f"Mapped '{workspace}' to 'prod:/public_html'.\n",
        "",
    )
    assert store.load().projects["prod"].local_root == str(workspace)


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
        run(["l"], store=store)


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
    docs = workspace / "docs"
    ignored.mkdir()
    docs.mkdir()
    package = ignored / "package"
    package.mkdir()
    (ignored / "drop.js").write_text("drop", encoding="utf-8")
    (ignored / "keep.js").write_text("keep", encoding="utf-8")
    (package / "nested.js").write_text("nested", encoding="utf-8")
    (workspace / "debug.log").write_text("debug", encoding="utf-8")
    (workspace / "composer.json").write_text("{}", encoding="utf-8")
    (workspace / "composer.lock").write_text("{}", encoding="utf-8")
    (docs / "note.txt").write_text("note", encoding="utf-8")

    status, stdout, stderr = invoke(["m", "prod"], store)
    exclude_result = invoke(
        ["exc", "--pattern", ".git/, node_modules/,*.log,**/.cache/"], store
    )
    expanded_exclude_result = invoke(
        ["exc", "composer.*"], store
    )
    include_result = invoke(["inc", "node_modules/keep.js"], store)
    directory_include_result = invoke(["inc", "node_modules/package"], store)
    monkeypatch.chdir(docs)
    assert invoke(["exc", "note.txt"], store)[0] == 0
    monkeypatch.chdir(workspace)

    assert status == 0 and stderr == ""
    assert stdout == f"Mapped '{workspace}' to 'prod:/public_html'.\n"
    assert exclude_result == (
        0,
        "Recorded exclusion rules for project 'prod':\n"
        "  1  exclude .git/**\n"
        "  2  exclude node_modules/**\n"
        "  3  exclude *.log\n"
        "  4  exclude **/.cache/**\n",
        "",
    )
    assert include_result == (
        0,
        "Recorded inclusion rules for project 'prod':\n"
        "  7  include ./node_modules/keep.js\n",
        "",
    )
    assert directory_include_result == (
        0,
        "Recorded inclusion rules for project 'prod':\n"
        "  8  include node_modules/package/**\n",
        "",
    )
    assert expanded_exclude_result == (
        0,
        "Recorded exclusion rules for project 'prod':\n"
        "  5  exclude ./composer.json\n"
        "  6  exclude ./composer.lock\n",
        "",
    )
    project = store.load().projects["prod"]
    assert project.local_root == str(workspace)
    assert project.rules == (
        SyncRule(1, "exclude", ".git/**"),
        SyncRule(2, "exclude", "node_modules/**"),
        SyncRule(3, "exclude", "*.log"),
        SyncRule(4, "exclude", "**/.cache/**"),
        SyncRule(5, "exclude", "composer.json"),
        SyncRule(6, "exclude", "composer.lock"),
        SyncRule(7, "include", "node_modules/keep.js"),
        SyncRule(8, "include", "node_modules/package/**"),
        SyncRule(9, "exclude", "docs/note.txt"),
    )
    assert project.next_rule_id == 10
    rules = RuleSet(project.rules)
    assert rules.excludes(".git", is_directory=True)
    assert not rules.excludes("node_modules/package/index.js")
    assert not rules.excludes("node_modules/keep.js")
    assert not rules.excludes("node_modules/package/nested.js")
    assert rules.excludes("debug.log")
    assert not rules.excludes("src/debug.log")
    assert not rules.excludes("src/main.py")
    snapshot = snapshot_local(workspace, rules)
    assert [entry.path for entry in snapshot.entries] == [
        "docs",
        "node_modules/keep.js",
        "node_modules/package",
        "node_modules/package/nested.js",
    ]
    included_view = (
        0,
        "Tracked local files for project 'prod':\n"
        "  node_modules/keep.js\n"
        "  node_modules/package/nested.js\n",
        "",
    )
    assert invoke(["tracked"], store) == included_view
    assert invoke(["exc"], store) == (
        0,
        "Exclusion rules for project 'prod':\n"
        "  1  exclude .git/**\n"
        "  2  exclude node_modules/**\n"
        "  3  exclude *.log\n"
        "  4  exclude **/.cache/**\n"
        "  5  exclude ./composer.json\n"
        "  6  exclude ./composer.lock\n"
        "  9  exclude ./docs/note.txt\n",
        "",
    )
    assert invoke(["inc"], store) == (
        0,
        "Inclusion rules for project 'prod':\n"
        "  7  include ./node_modules/keep.js\n"
        "  8  include node_modules/package/**\n",
        "",
    )
    list_stdout = invoke(["list"], store)[1]
    assert "* prod\n" in list_stdout
    assert f"  Local root: {workspace}\n" in list_stdout
    assert "  Rules:\n" in list_stdout
    assert "    1  exclude .git/**\n" in list_stdout
    assert "    8  include node_modules/package/**\n" in list_stdout
    assert "    9  exclude ./docs/note.txt\n" in list_stdout
    assert invoke(["rules", "remove", "8"], store) == (
        0,
        "Removed rule 8 from project 'prod': include node_modules/package/**\n",
        "",
    )
    assert store.load().projects["prod"].next_rule_id == 10
    assert invoke(["inc", "composer.json"], store) == (
        0,
        "Recorded inclusion rules for project 'prod':\n"
        "  10  include ./composer.json\n",
        "",
    )
    updated = store.load().projects["prod"]
    assert 5 not in {rule.id for rule in updated.rules}
    assert updated.next_rule_id == 11
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
    assert invoke(
        ["exclude", "--pattern", "node_modules/,**/*.log"], store
    )[0] == 0

    transports = []
    operations = []

    class FakeTransport:
        def __init__(self, project) -> None:
            transports.append(project)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(self, rules, selector=None, *, include_excluded=False):
            assert rules.rules == (
                SyncRule(1, "exclude", "node_modules/**"),
                SyncRule(2, "exclude", "**/*.log"),
            )
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
    push_comparison = invoke(["diff"], store)
    push_progress = (
        "Checking differences for project 'prod'...\n"
        "Connecting securely over FTPS...\n"
        "Scanning local files...\n"
        "Reading remote files over FTPS...\n"
        "Building push plan...\n"
    )
    assert push_comparison[0] == 0 and push_comparison[2] == push_progress
    assert "Local -> Remote for project 'prod':\n" in push_comparison[1]
    assert "+   README.md\n" in push_comparison[1]
    assert "-   deployed.html\n" in push_comparison[1]
    assert "!   linked\n" in push_comparison[1]
    assert "· d node_modules\n" in push_comparison[1]
    assert "·   node_modules/package.js\n" in push_comparison[1]
    assert "·   src/debug.log\n" in push_comparison[1]
    selected_comparison = invoke(["diff", "main.py"], store)
    assert selected_comparison[0] == 0
    assert selected_comparison[2] == push_progress
    assert "src/main.py" in selected_comparison[1]
    assert "README.md" not in selected_comparison[1]
    assert "deployed.html" not in selected_comparison[1]

    monkeypatch.chdir(workspace)
    expanded_comparison = invoke(
        ["diff", "README.md,src/main.py", "src"], store
    )
    assert expanded_comparison[0] == 0
    assert "+   README.md\n" in expanded_comparison[1]
    assert "+   src/main.py\n" in expanded_comparison[1]
    assert "+ d src\n" in expanded_comparison[1]

    colored_comparison = invoke(["diff", "**", "--color", "always"], store)
    assert "\033[32m+\033[0m \033[94md src\033[0m" in colored_comparison[1]
    assert "\033[90m·\033[0m \033[34md node_modules\033[0m" in (
        colored_comparison[1]
    )
    assert "\033[90m·   src/debug.log\033[0m" in colored_comparison[1]
    monkeypatch.chdir(source)

    pull_comparison = invoke(["diff", "--pull", "-p"], store)
    assert pull_comparison[0] == 0
    assert pull_comparison[2].endswith("Building pull plan...\n")
    assert "Remote -> Local for project 'prod':\n" in pull_comparison[1]
    assert "+   deployed.html\n" in pull_comparison[1]
    assert "-   README.md\n" in pull_comparison[1]

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
    assert len(transports) == 10


def test_map_confirms_replacement_and_rejects_overlapping_local_roots(
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
    assert invoke(["exclude", "--pattern", "*.log"], store)[0] == 0
    monkeypatch.chdir(child)
    overlap_status, _, overlap_error = invoke(["map", "staging"], store)
    monkeypatch.chdir(separate)
    declined = invoke(["map", "prod"], store)
    remapped = invoke(["map", "prod"], store, stdin="yes\n")

    assert overlap_status == 1
    assert "overlaps project 'prod'" in overlap_error
    assert str(root) in overlap_error and str(child) in overlap_error
    assert declined == (
        0,
        f"Project 'prod' is mapped to '{root}'. Change it to '{separate}'? [y/N] "
        f"Kept existing mapping '{root}' for 'prod'.\n",
        "",
    )
    assert remapped == (
        0,
        f"Project 'prod' is mapped to '{root}'. Change it to '{separate}'? [y/N] "
        f"Remapped 'prod' from '{root}' to '{separate}'.\n",
        "",
    )
    remapped_project = store.load().projects["prod"]
    assert remapped_project.local_root == str(separate)
    assert remapped_project.rules == (SyncRule(1, "exclude", "*.log"),)
    assert store.load().projects["staging"].local_root is None
