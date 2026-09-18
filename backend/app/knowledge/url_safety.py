import ipaddress
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from app.knowledge.contracts import MonitorBaseline, RetrievedSource
from app.knowledge.normalization import content_sha256, normalize_html


class UnsafeSourceUrl(ValueError):
    """Raised when a configured source URL could reach an unsafe destination."""


class SourceRetrievalError(RuntimeError):
    """Raised when an approved source cannot be retrieved within monitor limits."""


class HostResolver(Protocol):
    def resolve(self, hostname: str) -> tuple[str, ...]: ...


_MAX_REDIRECTS = 3
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 15.0
_USER_AGENT = "ImmigrationFlow-SourceMonitor/1.0 (+https://github.com/LeeKhim28/immigration-flow)"


def validate_public_https_url(
    url: str,
    allowed_hosts: frozenset[str],
    resolver: HostResolver,
) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeSourceUrl("source URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeSourceUrl("source URL must not include credentials")
    if parsed.hostname is None:
        raise UnsafeSourceUrl("source URL must include a hostname")

    hostname = parsed.hostname.rstrip(".").lower()
    approved_hosts = {host.rstrip(".").lower() for host in allowed_hosts}
    if hostname not in approved_hosts:
        raise UnsafeSourceUrl("source URL host is not approved")
    if parsed.port not in (None, 443):
        raise UnsafeSourceUrl("source URL must use the default HTTPS port")

    try:
        addresses = resolver.resolve(hostname)
    except Exception as error:
        raise UnsafeSourceUrl("source URL hostname could not be resolved") from error
    if not addresses:
        raise UnsafeSourceUrl("source URL hostname resolved to no addresses")

    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as error:
            raise UnsafeSourceUrl("source URL hostname resolved to an invalid address") from error
        if not parsed_address.is_global:
            raise UnsafeSourceUrl("source URL resolved to a non-public destination")


def retrieve_source(
    config: MonitorBaseline,
    client: httpx.Client,
    resolver: HostResolver,
) -> RetrievedSource:
    current_url = config.canonical_url
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    for redirect_count in range(_MAX_REDIRECTS + 1):
        validate_public_https_url(current_url, frozenset(config.allowed_hosts), resolver)
        try:
            with client.stream(
                "GET",
                current_url,
                headers=headers,
                auth=None,
                cookies={},
                follow_redirects=False,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if location is None:
                        raise SourceRetrievalError("redirect response did not include a location")
                    if redirect_count >= _MAX_REDIRECTS:
                        raise SourceRetrievalError("source URL exceeded redirect limit")
                    current_url = urljoin(current_url, location)
                    continue

                if response.status_code < 200 or response.status_code >= 300:
                    raise SourceRetrievalError("source returned a non-success response")
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > _MAX_RESPONSE_BYTES:
                    raise SourceRetrievalError("source response exceeded size limit")

                document = bytearray()
                for chunk in response.iter_bytes():
                    document.extend(chunk)
                    if len(document) > _MAX_RESPONSE_BYTES:
                        raise SourceRetrievalError("source response exceeded size limit")
        except SourceRetrievalError:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise SourceRetrievalError("source request failed") from error

        normalized = normalize_html(bytes(document), config.selector, config.strategy_version)
        return RetrievedSource(
            final_url=current_url,
            retrieved_at=datetime.now(UTC),
            normalized_content=normalized.decode("utf-8"),
            content_hash=content_sha256(normalized),
        )

    raise SourceRetrievalError("source URL exceeded redirect limit")
