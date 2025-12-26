"""Custom exceptions for the RPi Gardener application.

Provides a hierarchy of domain-specific exceptions for better error handling
and more informative error messages throughout the application.
"""


class RpiGardenerError(Exception):
    """Base exception for all application errors."""


class ConfigurationError(RpiGardenerError):
    """Raised when configuration validation fails."""


class DatabaseError(RpiGardenerError):
    """Base exception for database-related errors."""


class DatabaseNotConnectedError(DatabaseError):
    """Raised when attempting database operations without a connection."""

    def __init__(self, message: str = "Database not connected") -> None:
        super().__init__(message)


class ValidationError(RpiGardenerError):
    """Raised when input validation fails."""


class ThresholdValidationError(ValidationError):
    """Raised when threshold values are invalid."""


class NotificationError(RpiGardenerError):
    """Base exception for notification-related errors."""


class NotificationSendError(NotificationError):
    """Raised when sending a notification fails."""
