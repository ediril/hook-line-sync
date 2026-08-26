import io

import pytest

from hls import __version__
from hls.cli import run
from hls.config import ConfigurationStore
from hls.rules import RuleSet, SyncRule
from hls.snapshot import TreeEntry, TreeSnapshot, snapshot_local
from hls.transport import PathOperationError


class TerminalInput(io.StringIO):
    def isatty(self) -> bool:
        return True


def invoke(arguments, store, *, stdin="no\n"):
    input_stream = stdin if hasattr(stdin, "readline") else io.StringIO(stdin)
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
    assert "tracked" not in help_output
    assert "lsl" not in help_output
    assert "lsr" not in help_output
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
    assert "profile             show details for one profile" in help_output
    assert "profiles            list configured profiles" in help_output
    assert "list                list the current local directory" in help_output
    for command in ("exclude", "include"):
        rule_help = invoke(["help", command], store)[1]
        assert f"hls {command} [PATH ...]" in rule_help
        assert f"hls {command} --pattern PATTERN ..." in rule_help

    list_status, list_stdout, list_stderr = invoke(["profiles"], store)
    assert (list_status, list_stderr) == (0, "")
    assert list_stdout == "  client-site\n"
    assert invoke(["profile", "client-site"], store) == (
        0,
        "Profile 'client-site':\n"
        "  Protocol: FTPS\n"
        "  Host: ftp.example.com:21\n"
        "  Remote root: /public_html/site\n"
        "  Local root: not mapped\n"
        "  Username env: PROD_FTPS_USERNAME\n"
        "  Password env: PROD_FTPS_PASSWORD\n"
        "  Rules: 0\n",
        "",
    )

    assert invoke(["remove", "client-site"], store) == (
        0,
        "Removed project 'client-site'.\n",
        "",
    )
    assert invoke(["profiles"], store)[1] == "No profiles configured.\n"


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
        run(["p"], store=store)

    selected = invoke(["prof"], store, stdin=TerminalInput("2\n"))
    assert selected == (
        0,
        "'prof' matches multiple commands:\n\n"
        "  1. profile\n"
        "  2. profiles\n"
        "\nChoose a command [1-2]:   prod\n",
        "",
    )


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
    local_view = invoke(["list", "--recursive"], store)
    assert local_view[0] == 0 and local_view[2] == ""
    assert "  node_modules/keep.js\n" in local_view[1]
    assert "x composer.json\n" in local_view[1]
    assert "x docs/note.txt\n" in local_view[1]
    directory_view = invoke(["list", "node_modules"], store)
    assert "x node_modules/drop.js\n" in directory_view[1]
    assert "  node_modules/keep.js\n" in directory_view[1]
    assert "  node_modules/package/\n" in directory_view[1]
    assert "node_modules/package/nested.js" not in directory_view[1]
    assert "x node_modules/\n" not in directory_view[1]
    recursive_directory_view = invoke(
        ["list", "node_modules", "--recursive"], store
    )
    assert "  node_modules/package/nested.js\n" in recursive_directory_view[1]
    assert invoke(["exc"], store) == (
        0,
        "Exclusion rules for project 'prod':\n"
        "\n"
        "./\n"
        "  3  exclude *.log\n"
        "  5  exclude composer.json\n"
        "  6  exclude composer.lock\n"
        "\n"
        ".git/\n"
        "  1  exclude all contents\n"
        "\n"
        "docs/\n"
        "  9  exclude note.txt\n"
        "\n"
        "node_modules/\n"
        "  2  exclude all contents\n"
        "\n"
        "Everywhere\n"
        "  4  exclude .cache/**\n",
        "",
    )
    assert invoke(["inc"], store) == (
        0,
        "Inclusion rules for project 'prod':\n"
        "\n"
        "node_modules/\n"
        "  7  include keep.js\n"
        "\n"
        "node_modules/package/\n"
        "  8  include all contents\n",
        "",
    )
    rules_view = invoke(["rules"], store)
    assert rules_view[0] == 0
    assert rules_view[1].index("./\n") < rules_view[1].index(".git/\n")
    assert rules_view[1].index(".git/\n") < rules_view[1].index("docs/\n")
    assert "  2  exclude all contents\n  7  include keep.js\n" in rules_view[1]
    assert rules_view[1].endswith(
        "Higher rule IDs take precedence when rules overlap.\n"
    )
    list_stdout = invoke(["profiles"], store)[1]
    assert "* prod\n" in list_stdout
    profile_stdout = invoke(["profile"], store)[1]
    assert f"  Local root: {workspace}\n" in profile_stdout
    assert "  Rules: 9\n" in profile_stdout
    assert invoke(["rules", "remove", "8"], store) == (
        0,
        "Removed rule 8 from project 'prod': include node_modules/package/**\n",
        "",
    )
    assert store.load().projects["prod"].next_rule_id == 10
    assert invoke(["inc", "composer.json"], store) == (
        0,
        "Paths are included by the remaining policy for project 'prod';\n"
        "removed the unnecessary rules:\n"
        "  5  exclude ./composer.json\n",
        "",
    )
    updated = store.load().projects["prod"]
    assert 5 not in {rule.id for rule in updated.rules}
    assert not any(rule.pattern == "composer.json" for rule in updated.rules)
    assert updated.next_rule_id == 10
    assert "project mapped to the current directory" not in profile_stdout


def test_current_project_inference_drives_connect_and_tree_listings(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    source = workspace / "src"
    nested_source = source / "nested"
    ignored = workspace / "node_modules"
    outside = tmp_path / "outside"
    nested_source.mkdir(parents=True)
    ignored.mkdir()
    outside.mkdir()
    (workspace / "README.md").write_text("read me", encoding="utf-8")
    same = workspace / "same.txt"
    same.write_text("same", encoding="utf-8")
    (source / "main.py").write_text("print('hello')", encoding="utf-8")
    (source / ".env.example").write_text("KEY=value", encoding="utf-8")
    (source / "debug.log").write_text("ignored", encoding="utf-8")
    (nested_source / "child.py").write_text("child", encoding="utf-8")
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
    listed_directories = []

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

        def list_directory(self, relative_directory, rules):
            listed_directories.append(relative_directory.as_posix())
            assert rules.rules == (
                SyncRule(1, "exclude", "node_modules/**"),
                SyncRule(2, "exclude", "**/*.log"),
            )
            if relative_directory.as_posix() != ".":
                return TreeSnapshot()
            same_stat = same.stat()
            return TreeSnapshot(
                (
                    TreeEntry(
                        "deployed.html",
                        "file",
                        size=8,
                        modified_ns=1_700_000_000_000_000_000,
                        timestamp_precision_ns=1_000_000_000,
                    ),
                    TreeEntry(
                        "same.txt",
                        "file",
                        size=same_stat.st_size,
                        modified_ns=same_stat.st_mtime_ns,
                        timestamp_precision_ns=1,
                    ),
                    TreeEntry("src", "directory"),
                )
            )

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
        "  src/nested/\n"
        "  src/.env.example\n"
        "x src/debug.log\n"
        "  src/main.py\n",
        "",
    )
    assert invoke(["list"], store) == local_listing
    assert invoke(["ls"], store) == local_listing
    assert invoke(["list", "*"], store) == (
        0,
        "Local tree for project 'prod':\n"
        "  src/.env.example\n"
        "x src/debug.log\n"
        "  src/main.py\n"
        "  src/nested/child.py\n",
        "",
    )
    monkeypatch.chdir(workspace)
    recursive_list = invoke(["list", "--recursive"], store)
    assert "x node_modules/package.js\n" in recursive_list[1]
    assert "  src/.env.example\n" in recursive_list[1]
    assert recursive_list[1].index("x node_modules/\n") < (
        recursive_list[1].index("  src/\n")
    )
    assert recursive_list[1].index("  src/\n") < (
        recursive_list[1].index("  README.md\n")
    )
    colored_list = invoke(
        ["list", "--recursive", "--color", "always"], store
    )
    assert "\033[90mx src/debug.log\033[0m" in colored_list[1]
    assert "  \033[38;5;75msrc/\033[0m" in colored_list[1]
    assert "\033[90mx\033[0m \033[38;5;24mnode_modules/\033[0m" in (
        colored_list[1]
    )
    monkeypatch.chdir(source)
    push_comparison = invoke(["diff"], store)
    push_progress = (
        "Checking differences for project 'prod'...\n"
        "Connecting securely over FTPS...\n"
    )
    assert push_comparison[0] == 0 and push_comparison[2] == push_progress
    assert "+ main.py\n" in push_comparison[1]
    assert "+ nested/ ▸\n" in push_comparison[1]
    assert push_comparison[1].index("+ nested/ ▸\n") < (
        push_comparison[1].index("+ .env.example\n")
    )
    assert "src/nested/child.py" not in push_comparison[1]
    assert "README.md" not in push_comparison[1]
    assert "deployed.html" not in push_comparison[1]
    assert "linked" not in push_comparison[1]
    assert "node_modules" not in push_comparison[1]
    assert "same.txt" not in push_comparison[1]
    assert "x debug.log\n" in push_comparison[1]
    hidden_exclusions = invoke(["diff", "-i"], store)
    assert "debug.log" not in hidden_exclusions[1]

    recursive_comparison = invoke(["diff", "-r"], store)
    assert "  + child.py\n" in recursive_comparison[1]

    monkeypatch.chdir(workspace)
    pruned_comparison = invoke(
        ["diff", "--prune-remote", "--color", "always"], store
    )
    assert "\033[31m- deployed.html\033[0m\n" in pruned_comparison[1]
    assert "  \033[3;38;5;24msrc/ ▸\033[0m\n" in (
        pruned_comparison[1]
    )
    monkeypatch.chdir(source)
    selected_comparison = invoke(["diff", "main.py"], store)
    assert selected_comparison[0] == 0
    assert "main.py" in selected_comparison[1]
    assert "README.md" not in selected_comparison[1]
    assert "deployed.html" not in selected_comparison[1]

    monkeypatch.chdir(workspace)
    directory_comparison = invoke(["diff", "src"], store)
    assert "= src/\n" not in directory_comparison[1]
    assert "  src/\n" in directory_comparison[1]
    assert "  + nested/ ▸\n" in directory_comparison[1]
    assert "src/nested/child.py" not in directory_comparison[1]
    recursive_directory_comparison = invoke(["diff", "src", "-r"], store)
    assert "    + child.py\n" in recursive_directory_comparison[1]
    expanded_comparison = invoke(
        ["diff", "README.md,src/main.py", "src"], store
    )
    assert expanded_comparison[0] == 0
    assert "+ README.md\n" in expanded_comparison[1]
    assert "  + main.py\n" in expanded_comparison[1]
    assert "src/ ▸\n" not in expanded_comparison[1]

    colored_comparison = invoke(
        ["diff", "**", "--color", "always"], store
    )
    assert "  \033[38;5;75msrc/\033[0m" in colored_comparison[1]
    assert "\033[90mx\033[0m \033[38;5;24mnode_modules/\033[0m" in (
        colored_comparison[1]
    )
    assert "  \033[90mx debug.log\033[0m" in colored_comparison[1]
    assert "= same.txt" in colored_comparison[1]
    assert colored_comparison[1].index("node_modules/") < (
        colored_comparison[1].index("src/")
    )
    assert colored_comparison[1].index("src/") < (
        colored_comparison[1].index("README.md")
    )

    paged = invoke(["diff", ".", "--recursive", "--paged"], store)
    assert "Resume: hls diff . --recursive --paged --resume src\n" in paged[1]
    resumed = invoke(
        ["diff", ".", "--recursive", "--paged", "--resume", "src"], store
    )
    assert "main.py" in resumed[1]
    assert "--resume src/nested" in resumed[1]
    monkeypatch.chdir(workspace)

    pull_comparison = invoke(
        ["diff", "--pull", "-r", "--color", "always"], store
    )
    assert pull_comparison[0] == 0
    assert "\033[38;5;30mr deployed.html\033[0m\n" in pull_comparison[1]
    assert "\033[38;5;51ml README.md\033[0m\n" in pull_comparison[1]
    with pytest.raises(SystemExit):
        run(["diff", "--pull", "-p"], store=store)
    with pytest.raises(SystemExit):
        run(["pull", "-p"], store=store)
    with pytest.raises(SystemExit):
        run(["pull"], store=store)

    monkeypatch.chdir(source)
    recursive_push = invoke(["push"], store)
    assert recursive_push[0] == 0
    assert ("upload", "src/nested/child.py", b"child", 5, False) in operations
    operations.clear()

    monkeypatch.chdir(workspace)
    push_result = invoke(["push", "src"], store)
    assert push_result[0] == 0
    assert push_result[2].startswith("Preparing push for project 'prod'...\n")
    assert push_result[2].endswith("Executing push plan...\n")
    assert "Push completed for project 'prod': 4 change(s)." in push_result[1]
    assert operations == [
        ("mkdir", "src"),
        ("mkdir", "src/nested"),
        ("upload", "src/.env.example", b"KEY=value", 9, False),
        ("upload", "src/main.py", b"print('hello')", 14, False),
    ]
    pull_result = invoke(["pull", "deployed.html"], store)
    assert pull_result[0] == 0
    assert pull_result[2].startswith("Preparing pull for project 'prod'...\n")
    assert pull_result[2].endswith("Executing pull plan...\n")
    assert "Pull completed for project 'prod': 0 change(s)." in pull_result[1]
    assert "skip           remote-only" in pull_result[1]
    assert len(transports) == 16


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


def test_push_reports_partial_failure_after_continuing_independent_paths(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    blocked = workspace / "blocked"
    blocked.mkdir(parents=True)
    (blocked / "child.txt").write_text("blocked", encoding="utf-8")
    (workspace / "good.txt").write_text("good", encoding="utf-8")
    monkeypatch.chdir(workspace)
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
        stdin="yes\n",
    )

    uploads = []

    class PartiallyWritableTransport:
        def __init__(self, project):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(self, rules, selector=None, *, include_excluded=False):
            return TreeSnapshot()

        def make_directory(self, path):
            if path == "blocked":
                raise PathOperationError("550 Permission denied")

        def upload_file(
            self,
            source,
            path,
            *,
            size,
            modified_ns,
            replace,
        ):
            uploads.append((path, source.read()))

        def delete_path(self, path, *, is_directory):
            raise AssertionError("pruning was not requested")

    monkeypatch.setattr("hls.cli.ExplicitFTPSTransport", PartiallyWritableTransport)
    result = invoke(["push", "-r"], store)

    assert result[0] == 1
    assert uploads == [("good.txt", b"good")]
    assert result[1] == (
        "Push finished with errors for project 'prod': "
        "1 completed, 1 failed, 1 skipped.\n"
        "  failed  blocked: 550 Permission denied\n"
        "  skipped blocked/child.txt: parent directory 'blocked' is unavailable\n"
    )
