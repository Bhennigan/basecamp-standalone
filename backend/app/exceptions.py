"""Custom exceptions for the application."""


class TracecatNotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class TracecatValidationError(Exception):
    """Raised when validation fails."""
    pass

