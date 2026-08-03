from abc import ABC, abstractmethod
from typing import Iterator


class BaseConnector(ABC):
    """Reads raw data from a scraper's output and yields normalized dicts ready for MongoDB."""

    @abstractmethod
    def iter_posts(self) -> Iterator[dict]:
        """Yield one document per post/tweet/video."""

    @abstractmethod
    def iter_comments(self) -> Iterator[dict]:
        """Yield one document per comment/reply."""

    def platform(self) -> str:
        return self.__class__.__name__.replace("Connector", "").lower()
