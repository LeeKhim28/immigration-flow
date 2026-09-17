from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import pytest

from app.knowledge.contracts import MonitorBaseline
from app.knowledge.url_safety import (
    SourceRetrievalError,
    UnsafeSourceUrl,
    retrieve_source,
    validate_public_https_url,
)


class FakeResolver:
    def __init__(self, addresses_by_host: Mapping[str, tuple[str, ...]]) -> None:
        self.addresses_by_host = addresses_by_host

    def resolve(self, hostname: str) -> tuple[str, ...]:
        return self.addresses_by_host[hostname]


def _baseline(url: str, hosts: tuple[str, ...]) -> MonitorBaseline:
    return MonitorBaseline(
        source_id="MY-TEST-SOURCE",
        canonical_url=url,
        allowed_hosts=hosts,
        selector="#policy",
        strategy_version=1,
        approved_hash="a" * 64,
        captured_at=datetime(2026, 9, 17, tzinfo=UTC),
        git_commit_sha="b" * 40,
    )


@pytest.mark.parametrize(
    ("url", "addresses", "message"),
    [
        ("http://official.example/policy", {"official.example": ("8.8.8.8",)}, "HTTPS"),
        (
            "https://user:pass@official.example/policy",
            {"official.example": ("8.8.8.8",)},
            "credentials",
        ),
        ("https://unapproved.example/policy", {"unapproved.example": ("8.8.8.8",)}, "approved"),
        ("https://loopback.example/policy", {"loopback.example": ("127.0.0.1",)}, "non-public"),
        ("https://private.example/policy", {"private.example": ("10.0.0.8",)}, "non-public"),
        (
            "https://link-local.example/policy",
            {"link-local.example": ("169.254.4.9",)},
            "non-public",
        ),
        ("https://ipv6-local.example/policy", {"ipv6-local.example": ("::1",)}, "non-public"),
    ],
)
def test_validate_public_https_url_rejects_unsafe_destination(
    url: str,
    addresses: Mapping[str, tuple[str, ...]],
    message: str,
) -> None:
    resolver = FakeResolver(addresses)
    allowed_hosts = (
        frozenset({"official.example"})
        if url.startswith("https://unapproved.example")
        else frozenset(addresses)
    )

    with pytest.raises(UnsafeSourceUrl, match=message):
        validate_public_https_url(url, allowed_hosts, resolver)


def test_validate_public_https_url_accepts_allowlisted_public_host() -> None:
    resolver = FakeResolver({"official.example": ("8.8.8.8", "1.1.1.1")})

    validate_public_https_url(
        "https://official.example/policy",
        frozenset({"official.example"}),
        resolver,
    )


def test_retrieve_source_rejects_redirect_to_newly_resolved_private_address() -> None:
    resolver = FakeResolver({"official.example": ("8.8.8.8",), "internal.example": ("127.0.0.1",)})
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                302,
                headers={"Location": "https://internal.example/policy"},
                request=request,
            )
        )
    )

    with pytest.raises(UnsafeSourceUrl, match="non-public"):
        retrieve_source(
            _baseline(
                "https://official.example/policy",
                ("official.example", "internal.example"),
            ),
            client,
            resolver,
        )


def test_retrieve_source_rejects_more_than_three_redirects() -> None:
    resolver = FakeResolver({"official.example": ("8.8.8.8",)})

    def handler(request: httpx.Request) -> httpx.Response:
        redirect_number = int(request.url.path.rsplit("/", maxsplit=1)[-1])
        return httpx.Response(
            302,
            headers={"Location": f"https://official.example/redirect/{redirect_number + 1}"},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(SourceRetrievalError, match="redirect"):
        retrieve_source(
            _baseline("https://official.example/redirect/0", ("official.example",)),
            client,
            resolver,
        )


def test_retrieve_source_rejects_response_larger_than_five_mebibytes() -> None:
    resolver = FakeResolver({"official.example": ("8.8.8.8",)})
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"Content-Length": str(5 * 1024 * 1024 + 1)},
                request=request,
            )
        )
    )

    with pytest.raises(SourceRetrievalError, match="size"):
        retrieve_source(
            _baseline("https://official.example/policy", ("official.example",)),
            client,
            resolver,
        )
