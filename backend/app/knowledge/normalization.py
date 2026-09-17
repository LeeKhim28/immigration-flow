import hashlib
import re
import unicodedata

from bs4 import BeautifulSoup, Comment
from soupsieve import SelectorSyntaxError


class NormalizationError(ValueError):
    """Raised when source content cannot be normalized safely."""


_SUPPORTED_STRATEGY_VERSION = 1
_REMOVED_TAGS = ("script", "style", "nav", "noscript", "template")
_BANNER_MARKERS = ("cookie", "consent")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_html(document: bytes, selector: str | None, strategy_version: int) -> bytes:
    if strategy_version != _SUPPORTED_STRATEGY_VERSION:
        raise NormalizationError("unknown normalization strategy")

    soup = BeautifulSoup(document, "html.parser")
    try:
        content = soup.select_one(selector) if selector is not None else soup
    except SelectorSyntaxError as error:
        raise NormalizationError("invalid configured selector") from error

    if content is None:
        raise NormalizationError("configured selector did not match source content")

    for element in content.find_all(_REMOVED_TAGS):
        element.decompose()
    for comment in content.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for element in list(content.find_all()):
        if element.attrs is None:
            continue
        attributes = " ".join(
            f"{name} {' '.join(value) if isinstance(value, list) else value}"
            for name, value in element.attrs.items()
        ).lower()
        if any(marker in attributes for marker in _BANNER_MARKERS):
            element.decompose()

    text = unicodedata.normalize("NFC", content.get_text(" ", strip=True))
    normalized = _WHITESPACE_PATTERN.sub(" ", text).strip()
    if not normalized:
        raise NormalizationError("normalized source content is empty")
    return normalized.encode("utf-8")


def content_sha256(normalized: bytes) -> str:
    return hashlib.sha256(normalized).hexdigest()
