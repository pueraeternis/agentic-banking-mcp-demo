"""Domain entities for clients, accounts, and transfers."""

from pydantic import BaseModel, Field

from core.constants import DEFAULT_CURRENCY, TransferStatus


class Client(BaseModel):
    """Bank client."""

    id: int
    full_name: str
    phone: str


class Account(BaseModel):
    """Client account with balance in minor currency units."""

    id: int
    client_id: int
    currency: str = Field(default=DEFAULT_CURRENCY)
    balance_cents: int


class Transfer(BaseModel):
    """Money transfer between two accounts."""

    id: int
    from_account_id: int
    to_account_id: int
    amount_cents: int
    status: TransferStatus
    created_at: str
