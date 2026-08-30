import io

import pytest

from hlsync import __version__
from hlsync.cli import run
from hlsync.config import DEFAULT_GLOBAL_RULES, ConfigurationStore, GlobalRuleStore
from hlsync.rules import RuleSet, SyncRule
from hlsync.snapshot import TreeEntry, TreeSnapshot, snapshot_local
from hlsync.transport import PathOperationError


class TerminalInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class TerminalOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


def invoke(arguments, store, *, stdin="no\n", terminal_output=False):
    input_stream = stdin if hasattr(stdin, "readline") else io.StringIO(stdin)
    stdout = TerminalOutput() if terminal_output else io.StringIO()
    stderr = io.StringIO()
    status = run(
        arguments,
        store=store,
        stdin=input_stream,
        stdout=stdout,
        stderr=stderr,
    )
    return status, stdout.getvalue(), stderr.getvalue()


def test_profile_lifecycle_uses_production_credentials_and_version(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    monkeypatch.chdir(tmp_path)

    add_status, add_stdout, add_stderr = invoke(
        [
            "create",
            "client-site",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html/site",
            "--local-root",
            str(tmp_path),
        ],
        store,
    )
    version_status, version_stdout, version_stderr = invoke(["v"], store)

    assert (add_status, add_stdout, add_stderr) == (
        0,
        "Created FTPS profile 'client-site'.\n"
        f"Mapped '{tmp_path}' to 'client-site:/public_html/site'.\n",
        "",
    )
    assert (version_status, version_stdout, version_stderr) == (
        0,
        f"{__version__}\n",
        "",
    )
    profile = store.load().profiles["client-site"]
    assert profile.host == "ftp.example.com"
    assert profile.remote_root == "/public_html/site"
    assert profile.local_root == str(tmp_path)
    assert profile.username_env == "PROD_FTPS_USERNAME"
    assert profile.password_env == "PROD_FTPS_PASSWORD"

    help_output = invoke(["help"], store)[1]
    assert "create              create an FTPS profile" in help_output
    assert "add" not in help_output
    assert "--legend" in help_output
    assert "inside a mapped" in help_output
    assert "profile; prefix a command" in help_output
    assert "one-command override" in help_output
    assert "diff                preview file changes without modifying anything" in (
        help_output
    )
    assert "compare" not in help_output
    assert "list (ls)" not in help_output
    assert "tracked" not in help_output
    assert "lsl" not in help_output
    assert "lsr" not in help_output
    assert "explain" not in help_output
    assert "push                upload local changes to the remote profile" in (
        help_output
    )
    assert "root                print a profile's mapped local root" in help_output
    pull_help = (
        "pull                replace changed local files from the remote profile"
    )
    assert pull_help in help_output
    assert "usage: hlsync [PROFILE] diff" in invoke(["help", "d"], store)[1]
    assert "--color" not in invoke(["help", "list"], store)[1]
    diff_help = invoke(["help", "diff"], store)[1]
    assert "--color" not in diff_help
    assert "-a, --all" in diff_help
    assert "-k, --keep-remote" in diff_help
    assert "--prune-remote" not in diff_help
    push_help = invoke(["help", "push"], store)[1]
    assert "-k, --keep-remote" in push_help
    assert "--prune-remote" not in push_help
    profile_help = invoke(["help", "profile"], store)[1]
    assert "--details" in profile_help
    assert "--info" not in profile_help
    rules_help = invoke(["help", "rules"], store)[1]
    assert "hlsync [PROFILE] rules" in rules_help
    assert "hlsync [PROFILE] rules remove RULE_ID" in rules_help
    assert "--profile" not in rules_help
    assert "[{remove}] [rule_id]" not in rules_help
    assert "profile             show the current profile" in help_output
    assert "profiles            list configured profiles" in help_output
    assert "list                list the current local directory" in help_output
    map_help = invoke(["help", "map"], store)[1]
    assert "--local-root PATH" in map_help
    assert "--remote-root PATH" in map_help
    assert invoke(["--legend"], store) == (
        0,
        "Diff legend:\n"
        "  +  new locally\n"
        "  ~  modified\n"
        "  -  remote deletion authorized\n"
        "  r  remote-only, retained\n"
        "  l  local-only, retained\n"
        "  ?  conflict\n"
        "  =  unchanged file\n"
        "  x  excluded, absent remotely\n"
        "  !  excluded, present remotely\n"
        "  /  directory\n"
        "  ▸  contents not inspected\n",
        "",
    )
    for command in ("exclude", "include"):
        rule_help = invoke(["help", command], store)[1]
        assert f"hlsync [PROFILE] {command} [PATH ...]" in rule_help
        assert f"hlsync [PROFILE] {command} --pattern PATTERN ..." in rule_help
    profile_selection_commands = (
        "exclude",
        "include",
        "rules",
        "list",
        "diff",
        "push",
        "pull",
    )
    for command in profile_selection_commands:
        assert "--profile" not in invoke(["help", command], store)[1]

    list_status, list_stdout, list_stderr = invoke(["profiles"], store)
    assert (list_status, list_stderr) == (0, "")
    assert list_stdout == "* client-site\n"
    profile_details = (
        0,
        "Profile 'client-site':\n"
        "  Protocol: FTPS\n"
        "  Host: ftp.example.com:21\n"
        "  Remote root: /public_html/site\n"
        f"  Local root: {tmp_path}\n"
        "  Username env: PROD_FTPS_USERNAME\n"
        "  Password env: PROD_FTPS_PASSWORD\n"
        "  Rules: 0\n",
        "",
    )
    assert invoke(["profile"], store) == (0, "client-site\n", "")
    assert invoke(["profile", "--details"], store) == profile_details
    assert invoke(["profile", "client-site"], store) == (
        0,
        "client-site\n",
        "",
    )
    assert invoke(["profile", "client-site", "--details"], store) == (
        profile_details
    )
    assert invoke(["client-site", "profile"], store) == (
        0,
        "client-site\n",
        "",
    )
    assert invoke(["client-site", "profile", "--details"], store) == (
        profile_details
    )
    assert invoke(["root", "client-site"], store) == (0, f"{tmp_path}\n", "")

    assert invoke(["remove", "client-site"], store) == (
        0,
        "Removed profile 'client-site'.\n",
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
            "create",
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
        "Created FTPS profile 'prod'.\n"
        f"Mapped '{workspace}' to 'prod:/public_html'.\n",
        "",
    )
    assert store.load().profiles["prod"].local_root == str(workspace)


def test_add_prompts_for_another_local_root_when_current_is_declined(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    current = tmp_path / "current"
    selected = tmp_path / "selected"
    current.mkdir()
    selected.mkdir()
    monkeypatch.chdir(current)

    result = invoke(
        [
            "create",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
        ],
        store,
        stdin=f"no\n{selected}\n",
    )

    assert result == (
        0,
        f"Map current directory '{current}' to 'prod:/public_html'? [Y/n] "
        "What local folder should be mapped instead? "
        "Created FTPS profile 'prod'.\n"
        f"Mapped '{selected}' to 'prod:/public_html'.\n",
        "",
    )
    assert store.load().profiles["prod"].local_root == str(selected)


def test_global_rules_seed_outside_profiles_and_allow_profile_overrides(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / ".DS_Store").write_text("metadata", encoding="utf-8")
    (workspace / "scratch.tmp").write_text("temporary", encoding="utf-8")

    assert invoke(
        [
            "create",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
            "--local-root",
            str(workspace),
        ],
        store,
    )[0] == 0
    global_path = tmp_path / "rules.json"
    assert global_path.exists()
    assert GlobalRuleStore(global_path).load().rules == DEFAULT_GLOBAL_RULES
    assert '"next_rule_id"' not in global_path.read_text(encoding="utf-8")

    monkeypatch.chdir(outside)
    assert invoke(
        ["exclude", "-g", "--pattern", "*.tmp"], store
    ) == (
        0,
        "Recorded global exclusion rules:\n  g7  exclude *.tmp\n",
        "",
    )
    assert invoke(
        ["include", "-g", "--pattern", "**/.DS_Store"], store
    ) == (
        0,
        "Recorded global inclusion rules:\n"
        "  g8  include **/.DS_Store\n",
        "",
    )

    monkeypatch.chdir(workspace)
    excluded = invoke(["list"], store)[1]
    assert "x .DS_Store\n" not in excluded
    assert "x scratch.tmp\n" in excluded
    assert invoke(["include", "--pattern", "*.tmp"], store)[0] == 0
    included = invoke(["list"], store)[1]
    assert "x .DS_Store\n" not in included
    assert "x scratch.tmp\n" not in included
    combined = invoke(["rules"], store)[1]
    assert combined.index("Global synchronization rules:") < combined.index(
        "Synchronization rules for profile 'prod':"
    )
    assert "  g7  exclude *.tmp\n" in combined
    assert combined.endswith(
        "Global rules apply first; profile rules override them.\n"
    )
    invalid_global_id = invoke(["rules", "-g", "remove", "8"], store)
    assert invalid_global_id[0] == 1
    assert "rule id must be g-prefixed (for example g3)" in invalid_global_id[2]
    assert invoke(["rules", "-g", "remove", "g8"], store) == (
        0,
        "Removed global rule g8: include **/.DS_Store\n",
        "",
    )
    assert "x .DS_Store\n" not in invoke(["list"], store)[1]
    assert not any(
        rule.pattern == "**/.DS_Store"
        for rule in GlobalRuleStore(global_path).load().rules
    )
    assert invoke(
        ["exclude", "-g", "--pattern", "*.bak"], store
    ) == (
        0,
        "Recorded global exclusion rules:\n  g8  exclude *.bak\n",
        "",
    )


def test_cli_refuses_invalid_profile_mutations(tmp_path) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    arguments = [
        "create",
        "prod",
        "--host",
        "ftp.example.com",
        "--remote-root",
        "/public_html/site",
        "--local-root",
        str(tmp_path),
    ]
    assert invoke(arguments, store)[0] == 0

    duplicate_status, _, duplicate_error = invoke(arguments, store)
    missing_status, _, missing_error = invoke(["connect", "missing"], store)

    assert duplicate_status == 1 and "already exists" in duplicate_error
    assert missing_status == 1 and "does not exist" in missing_error
    with pytest.raises(SystemExit):
        run(["create", "unsafe", "--host", "ftp.example.com"], store=store)
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
            "create",
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
            "--local-root",
            str(tmp_path),
        ],
        store,
    )

    assert status == 0
    profile = store.load().profiles["staging"]
    assert (profile.type, profile.port, profile.username_env, profile.password_env) == (
        "ftps",
        2121,
        "SHARED_USER",
        "STAGING_SECRET",
    )


def test_ordered_exclusion_commands_persist_reinclusion(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    invoke(
        [
            "create",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
            "--local-root",
            str(workspace),
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

    assert exclude_result == (
        0,
        "Recorded exclusion rules for profile 'prod':\n"
        "  1  exclude .git/**\n"
        "  2  exclude node_modules/**\n"
        "  3  exclude *.log\n"
        "  4  exclude **/.cache/**\n",
        "",
    )
    assert include_result == (
        0,
        "Recorded inclusion rules for profile 'prod':\n"
        "  7  include ./node_modules/keep.js\n",
        "",
    )
    assert directory_include_result == (
        0,
        "Recorded inclusion rules for profile 'prod':\n"
        "  8  include node_modules/package/**\n",
        "",
    )
    assert expanded_exclude_result == (
        0,
        "Recorded exclusion rules for profile 'prod':\n"
        "  5  exclude ./composer.json\n"
        "  6  exclude ./composer.lock\n",
        "",
    )
    profile = store.load().profiles["prod"]
    assert profile.local_root == str(workspace)
    assert profile.rules == (
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
    rules = RuleSet(profile.rules)
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
    assert "    keep.js\n" in local_view[1]
    assert "x composer.json\n" in local_view[1]
    assert "  x note.txt\n" in local_view[1]
    directory_view = invoke(["list", "node_modules"], store)
    assert "  node_modules/\n" in directory_view[1]
    assert "  x drop.js\n" in directory_view[1]
    assert "    keep.js\n" in directory_view[1]
    assert "    package/\n" in directory_view[1]
    assert "nested.js" not in directory_view[1]
    assert "x node_modules/\n" not in directory_view[1]
    recursive_directory_view = invoke(
        ["list", "node_modules", "--recursive"], store
    )
    assert "      nested.js\n" in recursive_directory_view[1]
    assert invoke(["exc"], store) == (
        0,
        "Exclusion rules for profile 'prod':\n"
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
        "Inclusion rules for profile 'prod':\n"
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
    assert "Higher rule IDs take precedence when rules overlap.\n" in rules_view[1]
    assert rules_view[1].endswith(
        "Global rules apply first; profile rules override them.\n"
    )
    list_stdout = invoke(["profiles"], store)[1]
    assert "* prod\n" in list_stdout
    assert invoke(["profile"], store) == (0, "prod\n", "")
    profile_stdout = invoke(["profile", "--details"], store)[1]
    assert f"  Local root: {workspace}\n" in profile_stdout
    assert "  Rules: 9\n" in profile_stdout
    assert invoke(["root"], store) == (0, f"{workspace}\n", "")
    assert invoke(["rules", "remove", "8"], store) == (
        0,
        "Removed rule 8 from profile 'prod': include node_modules/package/**\n",
        "",
    )
    assert invoke(["inc", "composer.json"], store) == (
        0,
        "Paths are included by the remaining policy for profile 'prod';\n"
        "removed the unnecessary rules:\n"
        "  5  exclude ./composer.json\n",
        "",
    )
    updated = store.load().profiles["prod"]
    assert 5 not in {rule.id for rule in updated.rules}
    assert not any(rule.pattern == "composer.json" for rule in updated.rules)
    assert "profile mapped to the current directory" not in profile_stdout

    (workspace / "root.env").write_text("ROOT=1", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert invoke(["prod", "exclude", "*.env"], store) == (
        0,
        "Recorded exclusion rules for profile 'prod':\n"
        "  10  exclude ./root.env\n",
        "",
    )


def test_current_profile_inference_drives_connect_and_tree_listings(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
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
            "create",
            "prod",
            "--host",
            "ftp.example.com",
            "--remote-root",
            "/public_html",
            "--local-root",
            str(workspace),
        ],
        store,
    )
    monkeypatch.chdir(workspace)
    assert invoke(
        ["exclude", "--pattern", "node_modules/,**/*.log"], store
    )[0] == 0
    expected_rules = RuleSet.layered(
        DEFAULT_GLOBAL_RULES,
        store.load().profiles["prod"].rules,
    ).rules

    operations = []
    listed_directories = []
    snapshot_traversal = []

    class FakeTransport:
        def __init__(self, profile) -> None:
            del profile

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(
            self,
            rules,
            selector=None,
            *,
            include_excluded=False,
            traverse_excluded=False,
            artifact_recovery=None,
        ):
            snapshot_traversal.append(traverse_excluded)
            assert rules.rules == expected_rules
            entries = []
            if selector is None or selector.matches("deployed.html"):
                entries.append(
                    TreeEntry(
                        "deployed.html",
                        "file",
                        size=8,
                        modified_ns=1_700_000_000_000_000_000,
                        timestamp_precision_ns=1_000_000_000,
                    )
                )
            if selector is None or selector.matches("same.txt"):
                same_stat = same.stat()
                entries.append(
                    TreeEntry(
                        "same.txt",
                        "file",
                        size=same_stat.st_size,
                        modified_ns=same_stat.st_mtime_ns,
                        timestamp_precision_ns=1,
                    )
                )
            if include_excluded and (
                selector is None or selector.matches("src/debug.log")
            ):
                entries.append(
                    TreeEntry(
                        "src/debug.log",
                        "file",
                        size=7,
                        modified_ns=1_700_000_000_000_000_000,
                        timestamp_precision_ns=1_000_000_000,
                        excluded=True,
                    )
                )
            assert not traverse_excluded or include_excluded
            return TreeSnapshot(tuple(entries))

        def list_directory(self, relative_directory, rules):
            listed_directories.append(relative_directory.as_posix())
            assert rules.rules == expected_rules
            if relative_directory.as_posix() == "src":
                debug_stat = (source / "debug.log").stat()
                return TreeSnapshot(
                    (
                        TreeEntry(
                            "src/debug.log",
                            "file",
                            size=debug_stat.st_size,
                            modified_ns=debug_stat.st_mtime_ns,
                            timestamp_precision_ns=1,
                            excluded=True,
                        ),
                    )
                )
            if relative_directory.as_posix() != ".":
                return TreeSnapshot()
            same_stat = same.stat()
            return TreeSnapshot(
                (
                    TreeEntry("archive", "directory"),
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

    monkeypatch.setattr("hlsync.cli.ExplicitFTPSTransport", FakeTransport)
    monkeypatch.chdir(source)

    assert invoke(["connect"], store) == (
        0,
        "Verified secure connectivity to profile 'prod'.\n",
        "",
    )
    local_listing = (
        0,
        "Local tree for profile 'prod':\n"
        "  nested/\n"
        "  .env.example\n"
        "x debug.log\n"
        "  main.py\n",
        "",
    )
    assert invoke(["list"], store) == local_listing
    assert invoke(["ls"], store) == local_listing
    assert invoke(["list", "*"], store) == (
        0,
        "Local tree for profile 'prod':\n"
        "  nested/\n"
        "    child.py\n"
        "  .env.example\n"
        "x debug.log\n"
        "  main.py\n",
        "",
    )
    monkeypatch.chdir(workspace)
    recursive_list = invoke(["list", "--recursive"], store)
    assert "  x package.js\n" in recursive_list[1]
    assert "    .env.example\n" in recursive_list[1]
    assert recursive_list[1].index("x node_modules/\n") < (
        recursive_list[1].index("  src/\n")
    )
    assert recursive_list[1].index("  src/\n") < (
        recursive_list[1].index("  README.md\n")
    )
    included_only_list = invoke(["list", "--recursive", "-i"], store)
    assert (
        "Options: recursive (-r); included paths only (-i).\n"
        in included_only_list[1]
    )
    assert "package.js" not in included_only_list[1]
    assert "    .env.example\n" in included_only_list[1]
    colored_list = invoke(["list", "--recursive"], store, terminal_output=True)
    assert "  \033[90mx debug.log\033[0m" in colored_list[1]
    assert "  \033[38;5;75msrc/\033[0m" in colored_list[1]
    assert "\033[90mx\033[0m \033[38;5;24mnode_modules/\033[0m" in (
        colored_list[1]
    )
    monkeypatch.chdir(source)
    push_comparison = invoke(["diff"], store)
    push_progress = (
        "Checking differences for profile 'prod'...\n"
        "Connecting securely over FTPS...\n"
    )
    assert push_comparison[0] == 0 and push_comparison[2] == push_progress
    assert push_comparison[1].startswith("src/\n")
    assert "+ main.py\n" in push_comparison[1]
    assert "nested" not in push_comparison[1]
    assert "src/nested/child.py" not in push_comparison[1]
    assert "README.md" not in push_comparison[1]
    assert "deployed.html" not in push_comparison[1]
    assert "linked" not in push_comparison[1]
    assert "node_modules" not in push_comparison[1]
    assert "same.txt" not in push_comparison[1]
    assert "  - debug.log\n" in push_comparison[1]
    hidden_exclusions = invoke(["diff", "-i"], store)
    assert "  - debug.log\n" in hidden_exclusions[1]
    assert invoke(["prod", "diff", "same.txt"], store)[1] == (
        "  no differences\n"
    )

    recursive_comparison = invoke(["diff", "-r"], store)
    assert "Options: recursive (-r).\n" in recursive_comparison[2]
    assert "  + child.py\n" in recursive_comparison[1]
    assert recursive_comparison[1].index("nested/\n") < (
        recursive_comparison[1].index("  + child.py\n")
    )
    assert recursive_comparison[1].index("  + child.py\n") < (
        recursive_comparison[1].index("+ .env.example\n")
    )

    monkeypatch.chdir(workspace)
    pruned_comparison = invoke(["diff"], store, terminal_output=True)
    assert "Options:" not in pruned_comparison[2]
    assert "\033[31m- deployed.html\033[0m\n" in pruned_comparison[1]
    assert "archive/ ▸" in pruned_comparison[1]
    assert "\033[31m-\033[0m" in pruned_comparison[1]
    assert "src/" not in pruned_comparison[1]
    assert "same.txt" not in pruned_comparison[1]
    kept_comparison = invoke(["diff", "-k"], store, terminal_output=True)
    assert "Options: keep remote-only paths (-k).\n" in kept_comparison[2]
    assert "\033[38;5;30mr deployed.html\033[0m\n" in kept_comparison[1]
    explicit_shallow = invoke(["diff", "."], store, terminal_output=True)
    assert "archive/ ▸" in explicit_shallow[1]
    assert "\033[38;5;30mr\033[0m" in explicit_shallow[1]
    monkeypatch.chdir(source)
    selected_comparison = invoke(["diff", "main.py"], store)
    assert selected_comparison[0] == 0
    assert "main.py" in selected_comparison[1]
    assert "README.md" not in selected_comparison[1]
    assert "deployed.html" not in selected_comparison[1]

    monkeypatch.chdir(workspace)
    directory_comparison = invoke(["diff", "src"], store)
    assert "= src/\n" not in directory_comparison[1]
    assert directory_comparison[1].startswith("src/\n")
    assert "nested" not in directory_comparison[1]
    assert "src/nested/child.py" not in directory_comparison[1]
    recursive_directory_comparison = invoke(["diff", "src", "-r"], store)
    assert "    + child.py\n" in recursive_directory_comparison[1]
    nested_directory_comparison = invoke(["diff", "src/nested"], store)
    assert nested_directory_comparison[1].startswith("src/nested/\n")
    assert "  + child.py\n" in nested_directory_comparison[1]
    expanded_comparison = invoke(
        ["diff", "README.md,src/main.py", "src"], store
    )
    assert expanded_comparison[0] == 0
    assert "+ README.md\n" in expanded_comparison[1]
    assert "  + main.py\n" in expanded_comparison[1]
    assert "src/ ▸\n" not in expanded_comparison[1]

    colored_comparison = invoke(
        ["diff", "**", "--all"], store, terminal_output=True
    )
    assert "Options: all entries (-a).\n" in colored_comparison[2]
    assert "\033[38;5;75msrc/\033[0m" in colored_comparison[1]
    assert "\033[90mx\033[0m \033[38;5;24mnode_modules/\033[0m" in (
        colored_comparison[1]
    )
    assert "  \033[31m- debug.log\033[0m" in colored_comparison[1]
    assert "= same.txt" in colored_comparison[1]
    assert colored_comparison[1].index("node_modules/") < (
        colored_comparison[1].index("src/")
    )
    assert colored_comparison[1].index("src/") < (
        colored_comparison[1].index("README.md")
    )
    all_included = invoke(["diff", "**", "--all", "-i"], store)
    assert "= same.txt" in all_included[1]
    assert "  - debug.log\n" in all_included[1]
    with monkeypatch.context() as no_color:
        no_color.setenv("NO_COLOR", "1")
        uncolored_comparison = invoke(
            ["diff", "**", "--all"], store, terminal_output=True
        )
    assert "\033[" not in uncolored_comparison[1]

    paged = invoke(["diff", ".", "--recursive", "--paged"], store)
    assert (
        "Resume: hlsync diff . --recursive --paged --resume archive\n"
        in paged[1]
    )
    resumed = invoke(
        ["diff", ".", "--recursive", "--paged", "--resume", "src"], store
    )
    assert "main.py" in resumed[1]
    assert "--resume src/nested" in resumed[1]
    monkeypatch.chdir(workspace)

    pull_comparison = invoke(
        ["diff", "--pull", "-r"], store, terminal_output=True
    )
    assert pull_comparison[0] == 0
    assert "\033[38;5;30mr deployed.html\033[0m\n" in pull_comparison[1]
    assert "\033[38;5;51ml README.md\033[0m\n" in pull_comparison[1]
    with pytest.raises(SystemExit):
        run(["diff", "--pull", "-k"], store=store)
    with pytest.raises(SystemExit):
        run(["pull", "-k"], store=store)
    with pytest.raises(SystemExit):
        run(["pull"], store=store)

    monkeypatch.chdir(source)
    recursive_push = invoke(["push"], store)
    assert recursive_push[0] == 0
    assert ("upload", "src/nested/child.py", b"child", 5, False) in operations
    operations.clear()

    monkeypatch.chdir(workspace)
    push_result = invoke(["push", "src", "-k"], store)
    assert push_result[0] == 0
    assert push_result[2].startswith("Preparing push for profile 'prod'...\n")
    assert "Comparing local and remote files...\n" in push_result[2]
    assert push_result[2].endswith(
        "Pushing changes...\n"
        "  Creating src/\n"
        "  Adding   src/.env.example\n"
        "  Adding   src/main.py\n"
    )
    assert push_result[1] == (
        "Push complete: 3 changes.\n"
        "Remote-only paths retained by --keep-remote.\n"
    )
    assert operations == [
        ("mkdir", "src"),
        ("upload", "src/.env.example", b"KEY=value", 9, False),
        ("upload", "src/main.py", b"print('hello')", 14, False),
    ]
    unchanged_push = invoke(["push", "same.txt"], store)
    assert "Pushing changes..." not in unchanged_push[2]
    assert unchanged_push[1] == (
        "  Nothing to push; 1 file is up to date in this scope.\n"
    )
    operations.clear()
    pruned_exclusion = invoke(["push", "src/debug.log"], store)
    assert pruned_exclusion[0] == 0
    assert snapshot_traversal[-1] is False
    assert operations == [("delete", "src/debug.log", False)]
    assert "  Deleting src/debug.log\n" in pruned_exclusion[2]
    assert pruned_exclusion[1] == "Push complete: 1 change.\n"
    operations.clear()
    recursive_pruned_exclusion = invoke(
        ["push", "src/debug.log", "-r"],
        store,
    )
    assert recursive_pruned_exclusion[0] == 0
    assert (
        "Options: recursive (-r).\n"
        in recursive_pruned_exclusion[2]
    )
    assert snapshot_traversal[-1] is True
    assert operations == [("delete", "src/debug.log", False)]
    operations.clear()
    retained_push = invoke(["push", "deployed.html", "-k"], store)
    assert "Pushing changes..." not in retained_push[2]
    assert retained_push[1] == (
        "  Nothing to push.\n"
        "Remote-only paths retained by --keep-remote.\n"
    )
    pull_result = invoke(["pull", "deployed.html"], store)
    assert pull_result[0] == 0
    assert pull_result[2].startswith("Preparing pull for profile 'prod'...\n")
    assert "Comparing local and remote files...\n" in pull_result[2]
    assert "Pulling changes..." not in pull_result[2]
    assert pull_result[1] == (
        "  Nothing to pull.\n"
        "Remote-only paths not restored:\n"
        "  deployed.html\n"
    )

    monkeypatch.chdir(outside)
    assert invoke(["root", "prod"], store) == (0, f"{workspace}\n", "")
    assert invoke(["profile"], store) == (
        0,
        "No active profile. Use hlsync PROFILE COMMAND.\n",
        "",
    )
    outside_status, _, outside_error = invoke(["list"], store)
    assert outside_status == 1
    assert outside_error == (
        "hlsync: error: current directory is not inside a mapped profile; "
        "prefix the command with a profile (hlsync PROFILE COMMAND)\n"
    )
    prefixed_list = invoke(["prod", "list"], store)
    assert prefixed_list[0] == 0
    assert "  README.md\n" in prefixed_list[1]
    assert "secret.txt" not in prefixed_list[1]
    prefixed_diff = invoke(["prod", "diff", "src"], store)
    assert prefixed_diff[0] == 0
    assert prefixed_diff[1].startswith("src/\n")
    assert "  + main.py\n" in prefixed_diff[1]
    prefixed_page = invoke(["prod", "diff", ".", "-r", "--paged"], store)
    assert (
        "Resume: hlsync prod diff . --recursive --paged --resume archive\n"
        in prefixed_page[1]
    )


def test_map_confirms_replacement_and_rejects_overlapping_local_roots(
    tmp_path, monkeypatch
) -> None:
    store = ConfigurationStore(tmp_path / "configs.json")
    root = tmp_path / "root"
    child = root / "child"
    separate = tmp_path / "separate"
    staging_root = tmp_path / "staging"
    child.mkdir(parents=True)
    separate.mkdir()
    staging_root.mkdir()
    for name, local_root in (("prod", root), ("staging", staging_root)):
        invoke(
            [
                "create",
                name,
                "--host",
                "ftp.example.com",
                "--remote-root",
                f"/{name}",
                "--local-root",
                str(local_root),
            ],
            store,
        )

    monkeypatch.chdir(root)
    assert invoke(["exclude", "--pattern", "*.log"], store)[0] == 0
    monkeypatch.chdir(child)
    overlap_status, _, overlap_error = invoke(
        ["map", "staging"], store, stdin="yes\n"
    )
    monkeypatch.chdir(separate)
    declined = invoke(["prod", "map"], store)
    remapped = invoke(["map", "prod"], store, stdin="yes\n")
    remote_remapped = invoke(
        ["map", "prod", "--remote-root", "/production"],
        store,
        stdin="yes\n",
    )

    assert overlap_status == 1
    assert "overlaps profile 'prod'" in overlap_error
    assert str(root) in overlap_error and str(child) in overlap_error
    assert declined == (
        0,
        "Change mapping for profile 'prod'?\n"
        f"  Local root: {root} → {separate}\n"
        "Continue? [y/N] Kept profile 'prod' mapping unchanged.\n",
        "",
    )
    assert remapped == (
        0,
        "Change mapping for profile 'prod'?\n"
        f"  Local root: {root} → {separate}\n"
        "Continue? [y/N] Updated profile 'prod' mapping:\n"
        f"  Local root: {root} → {separate}\n",
        "",
    )
    assert remote_remapped == (
        0,
        "Change mapping for profile 'prod'?\n"
        "  Remote root: /prod → /production\n"
        "Continue? [y/N] Updated profile 'prod' mapping:\n"
        "  Remote root: /prod → /production\n",
        "",
    )
    remapped_profile = store.load().profiles["prod"]
    assert remapped_profile.local_root == str(separate)
    assert remapped_profile.remote_root == "/production"
    assert remapped_profile.rules == (SyncRule(1, "exclude", "*.log"),)
    assert store.load().profiles["staging"].local_root == str(staging_root)


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
            "create",
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
        def __init__(self, profile):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def snapshot(
            self,
            rules,
            selector=None,
            *,
            include_excluded=False,
            traverse_excluded=False,
            artifact_recovery=None,
        ):
            del traverse_excluded, artifact_recovery
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

    monkeypatch.setattr("hlsync.cli.ExplicitFTPSTransport", PartiallyWritableTransport)
    result = invoke(["push", "-r"], store)

    assert result[0] == 1
    assert uploads == [("good.txt", b"good")]
    assert result[1] == (
        "Push finished with errors for profile 'prod': "
        "1 completed, 1 failed, 1 skipped.\n"
        "  failed  blocked: 550 Permission denied\n"
        "  skipped blocked/child.txt: parent directory 'blocked' is unavailable\n"
    )
