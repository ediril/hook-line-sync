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
from hls.snapshot import snapshot_local
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
    authorizer.add_user("prod-user", "prod-password", os.fspath(root), perm="elr")

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
        snapshot = transport.snapshot(ExclusionSpec(("cache/", "*.log")))
        assert [(entry.path, entry.kind) for entry in snapshot.entries] == [
            ("assets", "directory"),
            ("assets/logo.svg", "file"),
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
