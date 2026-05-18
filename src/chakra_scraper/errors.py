"""Application-specific exceptions."""

from __future__ import annotations


class ChakraScraperError(Exception):
    """Base exception for expected scraper failures."""


class ConfigError(ChakraScraperError):
    """Raised when runtime or selector configuration is invalid."""


class AuthStateMissingError(ChakraScraperError):
    """Raised when the Playwright storage-state file is missing."""


class SafetyBoundaryError(ChakraScraperError):
    """Raised when a URL violates configured host/domain boundaries."""


class ExtractionError(ChakraScraperError):
    """Raised when extraction fails after retries."""
