from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from string import Template
from typing import Optional

from lnbits.db import FilterModel
from lnbits.helpers import is_valid_email_address
from pydantic import BaseModel, Field


class Webhook(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: str = ""
    data: str = ""

    def data_json(self, **kwargs) -> Optional[dict]:
        if not self.data:
            return None
        try:
            t = Template(self.data)
            return json.loads(t.substitute(**kwargs))
        except Exception as e:
            raise ValueError(f"Invalid JSON data for webhook: {e}") from e


class AuctionDuration(BaseModel):
    days: int = 7
    hours: int = 0
    minutes: int = 0

    def to_timedelta(self) -> timedelta:
        return timedelta(days=self.days, hours=self.hours, minutes=self.minutes)


class AuctionRoomConfig(BaseModel):
    duration: AuctionDuration = AuctionDuration()
    lock_webhook: Webhook = Webhook()
    unlock_webhook: Webhook = Webhook()
    transfer_webhook: Webhook = Webhook()


class CreateAuctionRoomData(BaseModel):
    fee_wallet_id: Optional[str] = None
    currency: str
    name: str
    description: str
    type: str = "auction"  # [auction, fixed_price]
    room_percentage: float = 10
    min_bid_up_percentage: float = 5
    is_open_room: bool = False

    def validate_data(self):
        if self.type not in ["auction", "fixed_price"]:
            raise ValueError("Auction Room type must be 'auction' or 'fixed_price'.")
        if self.room_percentage <= 0:
            raise ValueError("Auction Room percentage must be positive.")

        if self.type == "fixed_price":
            self.min_bid_up_percentage = 0
        else:
            if self.min_bid_up_percentage <= 0:
                raise ValueError("Auction Room bid up must be positive.")


class EditAuctionRoomData(CreateAuctionRoomData):
    id: str
    extra: AuctionRoomConfig

    def validate_data(self):
        super().validate_data()
        if self.extra.duration.to_timedelta().total_seconds() <= 0:
            raise ValueError("Auction Room duration must be positive.")
        if self.type == "fixed_price":
            self.extra.duration.days = 365


class PublicAuctionRoom(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    type: str = "auction"  # [auction, fixed_price]
    duration_seconds: int = Field(default=0, no_database=True)

    min_bid_up_percentage: float = 5
    room_percentage: float = 10

    @property
    def is_auction(self):
        return self.type == "auction"

    @property
    def is_fixed_price(self):
        return self.type == "fixed_price"


class AuctionRoom(PublicAuctionRoom):
    user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fee_wallet_id: str
    # is the room open for everyone who is logged in to add items
    is_open_room: bool = False

    extra: AuctionRoomConfig

    def __init__(self, **data):
        super().__init__(**data)
        self.duration_seconds = int(self.extra.duration.to_timedelta().total_seconds())


class CreateAuctionItem(BaseModel):
    name: str
    description: Optional[str] = None
    ln_address: Optional[str] = None
    ask_price: float = 0
    transfer_code: str


class PublicAuctionItem(BaseModel):
    id: str
    auction_room_id: str
    name: str
    active: bool = True
    description: Optional[str] = None
    ask_price: float = 0
    current_price: float = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    current_price_sat: float = Field(default=0, no_database=True)
    bid_count: int = Field(default=0, no_database=True)
    currency: str = Field(default="sat", no_database=True)
    next_min_bid: float = Field(default=0, no_database=True)
    time_left_seconds: int = Field(default=0, no_database=True)
    user_is_owner: bool = Field(default=False, no_database=True)
    user_is_participant: bool = Field(default=False, no_database=True)
    user_is_top_bidder: bool = Field(default=False, no_database=True)

    @property
    def time_left(self) -> timedelta:
        return self.expires_at.astimezone(timezone.utc) - datetime.now(timezone.utc)


class AuctionItemExtra(BaseModel):
    lock_code: Optional[str] = None
    # code required to check that the user is the owner of the item
    transfer_code: str
    # wallet where payments will be received
    wallet_id: str
    is_fee_paid: bool = False
    is_owner_paid: bool = False
    is_transfered_to_new_owner: bool = False
    is_unlocked: bool = False
    owner_ln_address: Optional[str] = None


class AuctionItem(PublicAuctionItem):
    user_id: str
    extra: AuctionItemExtra

    def to_public(self, user_id: Optional[str] = None) -> PublicAuctionItem:
        if self.user_id == user_id:
            self.user_is_owner = True
        return PublicAuctionItem(**self.dict())


class AuctionItemFilters(FilterModel):
    __search_fields__ = ["name"]

    __sort_fields__ = [
        "name",
        "created_at",
        "expires_at",
        "ask_price",
        "current_price",
    ]

    name: str | None
    ask_price: float | None
    current_price: float | None
    created_at: datetime | None
    expires_at: datetime | None


class BidRequest(BaseModel):
    memo: str
    ln_address: str | None = None
    amount: float

    def validate_data(self):
        if self.amount <= 0:
            raise ValueError("Bid amount must be positive.")
        if not self.memo.strip():
            raise ValueError("Memo is required.")
        if self.ln_address and not is_valid_email_address(self.ln_address):
            raise ValueError("Lightning Address is not valid.")


class BidResponse(BaseModel):
    id: str
    payment_hash: str
    payment_request: str


class PublicBid(BaseModel):
    id: str
    auction_item_id: str
    memo: str
    amount: float
    amount_sat: int
    paid: bool = False
    currency: str
    higher_bid_made: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_is_owner: bool = Field(default=False, no_database=True)


class Bid(PublicBid):
    user_id: str
    ln_address: str | None = None
    payment_hash: str

    def to_public(self, user_id: Optional[str] = None) -> PublicBid:
        if self.user_id == user_id:
            self.user_is_owner = True
        return PublicBid(**self.dict())


class BidFilters(FilterModel):
    __search_fields__ = ["memo"]

    __sort_fields__ = [
        "memo",
        "created_at",
        "amount",
        "amount_sat",
    ]

    memo: str | None
    created_at: datetime | None
    amount: float | None
    amount_sat: float | None


class PublicAuditEntry(BaseModel):
    entry_id: str
    data: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEntry(PublicAuditEntry):
    id: Optional[int] = None


class AuditEntryFilters(FilterModel):
    __search_fields__ = ["entry_id", "data"]

    __sort_fields__ = ["entry_id", "created_at"]

    entry_id: str | None
    data: str | None
    created_at: datetime | None
