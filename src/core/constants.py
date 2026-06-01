"""Domain constants for the banking demo."""

from enum import StrEnum

DEFAULT_CURRENCY = "RUB"


class TransferStatus(StrEnum):
    """Lifecycle states for a transfer."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
