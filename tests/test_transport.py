from __future__ import annotations

import os
import ssl
import subprocess
import threading

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.servers import FTPServer

from hls.comparison import build_comparison
from hls.config import ProjectConfiguration
from hls.exclusions import ExclusionSpec
from hls.selection import FileSelector
from hls.snapshot import snapshot_local
from hls.transfer import execute_transfer
from hls.transport import ExplicitFTPSTransport, TransportError


def test_missing_credentials_are_reported(monkeypatch) -> None:
    monkeypatch.delenv("PROD_FTPS_USERNAME", raising=False)
    monkeypatch.delenv("PROD_FTPS_PASSWORD", raising=False)
    transport = ExplicitFTPSTransport(
        ProjectConfiguration(
            host="localhost",
            remote_root="/",
            username_env="PROD_FTPS_USERNAME",
            password_env="PROD_FTPS_PASSWORD",
        )
    )

    with pytest.raises(TransportError, match="PROD_FTPS_USERNAME.*PROD_FTPS_PASSWORD"):
        transport.connect()


@pytest.fixture
def tls_ftp_server(tmp_path):
    certificate = tmp_path / "certificate.pem"
    private_key = tmp_path / "private-key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            os.fspath(private_key),
            "-out",
            os.fspath(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )

    root = tmp_path / "ftp-root"
    root.mkdir()
    authorizer = DummyAuthorizer()
    authorizer.add_user(
        "prod-user",
        "prod-password",
        os.fspath(root),
        perm="elradfmwMT",
    )

    class Handler(TLS_FTPHandler):
        pass

    Handler.authorizer = authorizer
    Handler.certfile = os.fspath(certificate)
    Handler.keyfile = os.fspath(private_key)
    Handler.tls_control_required = True
    Handler.tls_data_required = True

    server = FTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"timeout": 0.05, "blocking": True, "handle_exit": False},
        daemon=True,
    )
    thread.start()
    try:
        yield server.socket.getsockname()[1], certificate, root
    finally:
        server.ioloop.call_later(0, server.close_all)
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_connects_with_verified_explicit_tls_and_protected_data_channel(
    tls_ftp_server, monkeypatch
) -> None:
    port, certificate, root = tls_ftp_server
    assets = root / "assets"
    cache = root / "cache"
    assets.mkdir()
    cache.mkdir()
    (assets / "logo.svg").write_text("logo", encoding="utf-8")
    (cache / "index.bin").write_bytes(b"ignored")
    (cache / "keep.bin").write_bytes(b"included")
    (root / "debug.log").write_text("ignored", encoding="utf-8")
    local_root = root.parent / "local-root"
    local_root.mkdir()
    (local_root / "local.txt").write_text("local", encoding="utf-8")
    monkeypatch.setenv("PROD_FTPS_USERNAME", "prod-user")
    monkeypatch.setenv("PROD_FTPS_PASSWORD", "prod-password")
    context = ssl.create_default_context(cafile=os.fspath(certificate))
    transport = ExplicitFTPSTransport(
        ProjectConfiguration(
            host="localhost",
            remote_root="/",
            port=port,
            username_env="PROD_FTPS_USERNAME",
            password_env="PROD_FTPS_PASSWORD",
        ),
        ssl_context=context,
    )

    with transport:
        # The fixture refuses unprotected data connections, so recursive MLSD
        # success proves that PROT P was negotiated rather than merely called.
        snapshot = transport.snapshot(
            ExclusionSpec(("cache/", "*.log", "!cache/keep.bin"))
        )
        assert [(entry.path, entry.kind) for entry in snapshot.entries] == [
            ("assets", "directory"),
            ("assets/logo.svg", "file"),
            ("cache/keep.bin", "file"),
        ]
        local = snapshot_local(local_root, ExclusionSpec())
        comparison = {
            entry.path: entry
            for entry in build_comparison(local, snapshot).entries
        }
        assert comparison["local.txt"].action == "upload"
        assert comparison["assets/logo.svg"].action == "skip"

    assert transport._client is None


def test_rejects_an_untrusted_server_certificate(tls_ftp_server, monkeypatch) -> None:
    port, _, _ = tls_ftp_server
    monkeypatch.setenv("PROD_FTPS_USERNAME", "prod-user")
    monkeypatch.setenv("PROD_FTPS_PASSWORD", "prod-password")
    transport = ExplicitFTPSTransport(
        ProjectConfiguration(
            host="localhost",
            remote_root="/",
            port=port,
            username_env="PROD_FTPS_USERNAME",
            password_env="PROD_FTPS_PASSWORD",
        )
    )

    with pytest.raises(TransportError, match="certificate verify failed"):
        transport.connect()


def test_rejects_an_inaccessible_project_root(tls_ftp_server, monkeypatch) -> None:
    port, certificate, _ = tls_ftp_server
    monkeypatch.setenv("PROD_FTPS_USERNAME", "prod-user")
    monkeypatch.setenv("PROD_FTPS_PASSWORD", "prod-password")
    context = ssl.create_default_context(cafile=os.fspath(certificate))
    transport = ExplicitFTPSTransport(
        ProjectConfiguration(
            host="localhost",
            remote_root="/missing",
            port=port,
            username_env="PROD_FTPS_USERNAME",
            password_env="PROD_FTPS_PASSWORD",
        ),
        ssl_context=context,
    )

    with pytest.raises(TransportError, match="No such file or directory"):
        transport.connect()


def test_selected_push_pull_and_remote_prune_use_the_shared_plan(
    tls_ftp_server, tmp_path, monkeypatch
) -> None:
    port, certificate, remote_root = tls_ftp_server
    local_root = tmp_path / "local"
    nested = local_root / "nested"
    nested.mkdir(parents=True)
    selected = nested / "selected.txt"
    selected.write_text("local version", encoding="utf-8")
    local_timestamp_ns = 1_700_000_000_000_000_000
    os.utime(selected, ns=(local_timestamp_ns, local_timestamp_ns))
    (local_root / "unselected.txt").write_text("stay local", encoding="utf-8")
    monkeypatch.setenv("PROD_FTPS_USERNAME", "prod-user")
    monkeypatch.setenv("PROD_FTPS_PASSWORD", "prod-password")
    context = ssl.create_default_context(cafile=os.fspath(certificate))
    transport = ExplicitFTPSTransport(
        ProjectConfiguration(host="localhost", remote_root="/", port=port),
        ssl_context=context,
    )

    with transport:
        exclusions = ExclusionSpec()
        unrelated = remote_root / "unrelated" / "deep"
        unrelated.mkdir(parents=True)
        (unrelated / "ignored.txt").write_text("ignored", encoding="utf-8")
        (remote_root / "top.txt").write_text("top", encoding="utf-8")
        assert transport._client is not None
        original_mlsd = transport._client.mlsd
        listed_directories = []

        def tracked_mlsd(path="", facts=()):
            listed_directories.append(path)
            return original_mlsd(path, facts)

        transport._client.mlsd = tracked_mlsd
        transport.snapshot(exclusions, FileSelector("*"))
        assert listed_directories == [""]

        selector = FileSelector("nested/*.txt")
        local = snapshot_local(local_root, exclusions, selector)
        remote = transport.snapshot(exclusions, selector)
        push = build_comparison(
            local,
            remote,
            selector=selector,
        )
        execute_transfer(
            push,
            local_root=local_root,
            local=local,
            remote=remote,
            transport=transport,
        )
        assert (remote_root / "nested" / "selected.txt").read_text() == (
            "local version"
        )
        assert not (remote_root / "unselected.txt").exists()
        remote = transport.snapshot(exclusions, selector)
        after_push = build_comparison(
            snapshot_local(local_root, exclusions, selector),
            remote,
            selector=selector,
        )
        assert after_push.entries[0].action == "unchanged"

        remote_selected = remote_root / "nested" / "selected.txt"
        remote_selected.write_text("remote version", encoding="utf-8")
        remote_timestamp_ns = local_timestamp_ns + 10_000_000_000
        os.utime(
            remote_selected,
            ns=(remote_timestamp_ns, remote_timestamp_ns),
        )
        local = snapshot_local(local_root, exclusions, selector)
        remote = transport.snapshot(exclusions, selector)
        pull = build_comparison(
            local,
            remote,
            direction="pull",
            selector=selector,
        )
        execute_transfer(
            pull,
            local_root=local_root,
            local=local,
            remote=remote,
            transport=transport,
        )
        assert selected.read_text(encoding="utf-8") == "remote version"
        assert selected.stat().st_mtime_ns == remote_timestamp_ns

        orphan = remote_root / "orphan.txt"
        orphan.write_text("delete me", encoding="utf-8")
        orphan_selector = FileSelector("orphan.txt")
        local = snapshot_local(local_root, exclusions, orphan_selector)
        remote = transport.snapshot(exclusions, orphan_selector)
        prune = build_comparison(
            local,
            remote,
            prune_remote=True,
            selector=orphan_selector,
        )
        execute_transfer(
            prune,
            local_root=local_root,
            local=local,
            remote=remote,
            transport=transport,
        )
        assert not orphan.exists()
