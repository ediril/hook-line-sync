from __future__ import annotations

import ftplib
import os
import ssl
from dataclasses import dataclass
from typing import Protocol

from hls.config import ProjectConfiguration


class TransportError(RuntimeError):
    """Raised when a remote transport cannot be used safely."""


class RemoteTransport(Protocol):
    def connect(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class ExplicitFTPSTransport:
    configuration: ProjectConfiguration
    timeout: float = 30.0
    ssl_context: ssl.SSLContext | None = None

    def __post_init__(self) -> None:
        self._client: ftplib.FTP_TLS | None = None

    def connect(self) -> None:
        username = os.environ.get(self.configuration.username_env)
        password = os.environ.get(self.configuration.password_env)
        missing = [
            name
            for name, value in (
                (self.configuration.username_env, username),
                (self.configuration.password_env, password),
            )
            if value is None
        ]
        if missing:
            raise TransportError(
                f"missing credential environment variable(s): {', '.join(missing)}"
            )

        client = ftplib.FTP_TLS(
            context=self.ssl_context or ssl.create_default_context(),
            timeout=self.timeout,
        )
        try:
            client.connect(self.configuration.host, self.configuration.port)
            client.auth()
            client.login(username, password)
            client.prot_p()
            client.cwd(self.configuration.remote_root)
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            try:
                client.close()
            finally:
                raise TransportError(
                    f"could not open explicit FTPS project at "
                    f"{self.configuration.host}:{self.configuration.port}"
                    f"{self.configuration.remote_root}: {error}"
                ) from error
        self._client = client

    def close(self) -> None:
        if self._client is None:
            return
        client, self._client = self._client, None
        try:
            client.quit()
        except (OSError, ftplib.Error):
            client.close()

    def __enter__(self) -> ExplicitFTPSTransport:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
