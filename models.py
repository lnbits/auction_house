from __future__ import annotations

from datetime import datetime
from typing import Optional

from lnbits.db import FilterModel
from pydantic import BaseModel, Field


class AuctionRoomConfig(BaseModel):
    only_creator_can_add: bool = True


class CreateAuctionRoomData(BaseModel):
    wallet: str
    currency: str
    name: str
    description: str
    type: str = "auction"  # [auction, fixed_price]
    days: int = 7
    room_percentage: float = 10
    min_bid_up_percentage: float = 5

    def validate_data(self):
        assert self.days > 0, "Auction Room days must be positive."
        assert self.room_percentage > 0, "Auction Room percentage must be positive."
        assert self.min_bid_up_percentage > 0, "Auction Room bid up must be positive."
        assert self.type in [
            "auction",
            "fixed_price",
        ], "Auction Room type must be 'auction' or 'fixed_price'."


class EditAuctionRoomData(CreateAuctionRoomData):
    id: str


class PublicAuctionRoom(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    type: str = "auction"  # [auction, fixed_price]
    days: int = 7
    room_percentage: float = 10
    min_bid_up_percentage: float = 5


class AuctionRoom(PublicAuctionRoom):
    user_id: str
    created_at: datetime
    wallet: str

    extra: AuctionRoomConfig


class CreateAuctionItem(BaseModel):
    name: str
    description: Optional[str] = None
    starting_price: float = 0
    transfer_code: str


class PublicAuctionItem(BaseModel):
    id: str
    auction_room_id: str
    name: str
    active: bool = True
    description: Optional[str] = None
    starting_price: float = 0
    created_at: datetime
    expires_at: datetime
    current_price: float
    current_price_sat: float = Field(default=0, no_database=True)
    bid_count: int = Field(default=0, no_database=True)
    currency: str = Field(default="sat", no_database=True)
    next_min_bid: float = Field(default=0, no_database=True)
    time_left_seconds: int = Field(default=0, no_database=True)


class AuctionItemExtra(BaseModel):
    currency: Optional[str] = None


class AuctionItem(PublicAuctionItem):
    user_id: str
    # code required to check that the user is the owner of the item
    transfer_code: str
    extra: AuctionItemExtra = AuctionItemExtra()


class AuctionItemFilters(FilterModel):

    __search_fields__ = [
        "name",
        "created_at",
        "expires_at",
        "starting_price",
        "current_price",
    ]

    __sort_fields__ = [
        "name",
        "created_at",
        "expires_at",
        "starting_price",
        "current_price",
    ]

    name: str | None
    starting_price: float | None
    current_price: float | None
    created_at: datetime | None
    expires_at: datetime | None


class BidRequest(BaseModel):
    memo: str
    amount: float


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
    currency: str
    higher_bid_made: bool = False
    created_at: datetime


class Bid(PublicBid):
    user_id: str
    paid: bool = False
    payment_hash: str
    expires_at: datetime


class BidFilters(FilterModel):
    __search_fields__ = [
        "memo",
        "created_at",
        "amount",
        "amount_sat",
    ]

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
