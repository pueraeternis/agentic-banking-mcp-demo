"""Application error hierarchy for banking use cases."""


class AppError(Exception):
    """Base application error with a stable machine code."""

    code: str = "APP_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ClientNotFound(AppError):
    """Client search returned no matches."""

    code = "CLIENT_NOT_FOUND"


class AccountNotFound(AppError):
    """Account id does not exist."""

    code = "ACCOUNT_NOT_FOUND"


class InsufficientFunds(AppError):
    """Source account cannot cover the transfer amount."""

    code = "INSUFFICIENT_FUNDS"


class InvalidTransferState(AppError):
    """Transfer is not in a state that allows the requested operation."""

    code = "INVALID_TRANSFER_STATE"


class TransferNotFound(AppError):
    """Transfer id does not exist."""

    code = "TRANSFER_NOT_FOUND"
