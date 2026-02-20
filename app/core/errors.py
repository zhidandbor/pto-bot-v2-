from __future__ import annotations


class CoreError(Exception):
    pass


class ForbiddenError(CoreError):
    pass


class NotFoundError(CoreError):
    pass


class ValidationError(CoreError):
    pass


class GroupNotRegisteredError(CoreError):
    pass


class PrivateNotAllowedError(CoreError):
    pass


class ContextSelectionRequiredError(CoreError):
    def __init__(self, *, message: str) -> None:
        super().__init__(message)
        self.message = message