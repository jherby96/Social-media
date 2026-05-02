"""Abstract base class for all platform connectors."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PostResult:
    success: bool
    platform_post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class BasePlatform(ABC):
    name: str = "base"
    max_chars: int = 5000
    supports_images: bool = False
    supports_videos: bool = False

    @abstractmethod
    def post(self, content: str, image_url: Optional[str] = None) -> PostResult:
        """Publish content to the platform."""

    def validate_content(self, content: str) -> tuple[bool, str]:
        if len(content) > self.max_chars:
            return False, f"Content exceeds {self.max_chars} character limit ({len(content)} chars)"
        if not content.strip():
            return False, "Content cannot be empty"
        return True, ""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
