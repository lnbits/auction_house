from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import Enum
from string import Template
from typing import Optional

from lnbits.db import FilterModel
from lnbits.helpers import is_valid_email_address
from pydantic import BaseModel, Field, validator


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


class AuctionTypes(str, Enum):
    auction = "auction"
    fixed_price = "fixed_price"


class CreateAuctionRoomData(BaseModel):
    wallet_id: str
    fee_wallet_id: Optional[str] = None
    currency: str
    name: str
    description: str
    auction_type: AuctionTypes = AuctionTypes.auction
    room_percentage: float = Field(default=10, ge=0, le=100)
    min_bid_up_percentage: float = Field(default=5, ge=0, le=100)
    is_open_room: bool = False


class EditAuctionRoomData(CreateAuctionRoomData):
    id: str
    extra: AuctionRoomConfig

    @validator("extra")
    def validate_extra_data(self):
        if self.extra.duration.to_timedelta().total_seconds() <= 0:
            raise ValueError("Auction Room duration must be positive.")
        if self.auction_type == AuctionTypes.fixed_price:
            self.extra.duration.days = 365


class PublicAuctionRoom(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    auction_type: AuctionTypes = AuctionTypes.auction
    duration_seconds: int = Field(default=0, no_database=True)

    min_bid_up_percentage: float = 5
    room_percentage: float = 10

    @property
    def is_auction(self):
        return self.auction_type == AuctionTypes.auction

    @property
    def is_fixed_price(self):
        return self.auction_type == AuctionTypes.fixed_price


class AuctionRoom(PublicAuctionRoom):
    user_id: str
    created_at: datetime
    wallet_id: str
    fee_wallet_id: str
    # is the room open for everyone who is logged in to add items
    is_open_room: bool = False

    extra: AuctionRoomConfig

    def __init__(self, **data):
        super().__init__(**data)
        self.duration_seconds = int(self.extra.duration.to_timedelta().total_seconds())


class CreateAuctionItem(BaseModel):
    name: str
    transfer_code: str
    ask_price: float = Field(default=0, ge=0)
    description: Optional[str] = None
    ln_address: Optional[str] = None


class PublicAuctionItem(BaseModel):
    id: str
    auction_room_id: str
    name: str
    active: bool = True
    description: Optional[str] = None
    ask_price: float = Field(default=0, ge=0)
    current_price: float = 0
    created_at: datetime
    expires_at: datetime
    current_price_sat: float = Field(default=0, no_database=True)
    bid_count: int = Field(default=0, no_database=True)
    currency: str = Field(default="sat", no_database=True)
    next_min_bid: float = Field(default=0, no_database=True)
    time_left_seconds: int = Field(default=0, no_database=True)
    is_mine: bool = Field(default=False, no_database=True)


class AuctionItemExtra(BaseModel):
    currency: Optional[str] = None
    lock_code: Optional[str] = None
    is_fee_paid: bool = False
    is_owner_paid: bool = False
    owner_ln_address: Optional[str] = None


class AuctionItem(PublicAuctionItem):
    user_id: str
    # code required to check that the user is the owner of the item
    transfer_code: str
    extra: AuctionItemExtra = AuctionItemExtra()

    def to_public(self, user_id: Optional[str] = None) -> PublicAuctionItem:
        if self.user_id == user_id:
            self.is_mine = True
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
    amount: float = Field(default=0, ge=0)
    ln_address: str | None = None

    @validator("ln_address")
    def validate_ln_address(self):
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
    created_at: datetime
    is_mine: bool = Field(default=False, no_database=True)


class Bid(PublicBid):
    user_id: str
    ln_address: str | None = None
    payment_hash: str
    expires_at: datetime

    def to_public(self, user_id: Optional[str] = None) -> PublicBid:
        if self.user_id == user_id:
            self.is_mine = True
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
