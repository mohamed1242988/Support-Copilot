from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """
    A normalized representation of any retrieved information.

    Every retrieval source (Freshdesk, Jira, Help Center, Internal KCS,
    Product Documentation, etc.) should return a Document object so that
    downstream components do not need to know where the data originated.
    """

    id: str
    source: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Safely retrieve a metadata value.

        Example:
            priority = document.get_metadata("priority")
        """
        return self.metadata.get(key, default)