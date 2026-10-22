"""Domain exceptions used by application services."""


class IngestionValidationError(ValueError):
    """Raised when the uploaded CSV cannot be safely processed."""
