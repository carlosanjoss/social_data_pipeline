from typing import Iterator

from connectors import BaseConnector


def extract_posts(connector: BaseConnector) -> Iterator[dict]:
    """Yield all post documents from a connector."""
    yield from connector.iter_posts()


def extract_comments(connector: BaseConnector) -> Iterator[dict]:
    """Yield all comment documents from a connector."""
    yield from connector.iter_comments()
