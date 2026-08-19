"""URI converter utilities.

Provides conversion between filesystem paths and file:// URIs
according to RFC 3986.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, unquote_plus
from urllib.request import url2pathname

_SublimePath = str
"""Sublime Text file path compatibility."""

URI = str
"""Uniform Resource Identifier (RFC 3986)."""

DocumentURI = URI
"""URI with scheme='file'."""


@lru_cache(128)
def path_to_uri(path: _SublimePath) -> DocumentURI:
    """Convert a filesystem path to a file:// URI.

    Args:
        path: Path object representing a local file.

    Returns:
        DocumentURI: A file:// URI string.
    """
    return Path(path).as_uri()


@lru_cache(128)
def uri_to_path(uri: DocumentURI) -> _SublimePath:
    """Convert a file:// URI to a filesystem path.

    Args:
        uri: A file:// URI string.

    Returns:
        Path: The corresponding filesystem path.

    Raises:
        ValueError: If the URI scheme is not 'file'.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Invalid URI scheme '{parsed.scheme}', expected 'file'")
    return str(Path(url2pathname(unquote_plus(parsed.path))))
