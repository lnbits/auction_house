from __future__ import annotations

from datetime import datetime
from typing import Optional

from lnbits.db import FilterModel
from pydantic import BaseModel, Field


class AuctionHouseConfig(BaseModel):
    bla: int = 1


class CreateAuctionHouseData(BaseModel):
    wallet: str
    currency: str
    name: str
    description: str
    type: str = "auction"  # [auction, fixed_price]
    days: int = 7
    house_percentage: float = 10
    min_bid_up_percentage: float = 5

    def validate_data(self):
        assert self.days > 0, "Auction House days must be positive."
        assert self.house_percentage > 0, "Auction House percentage must be positive."
        assert self.min_bid_up_percentage > 0, "Auction House bid up must be positive."
        assert self.type in [
            "auction",
            "fixed_price",
        ], "Auction House type must be 'auction' or 'fixed_price'."


class EditAuctionHouseData(CreateAuctionHouseData):
    id: str


class PublicAuctionHouse(BaseModel):
    id: str
    name: str
    description: str
    currency: str
    type: str = "auction"  # [auction, fixed_price]
    days: int = 7
    house_percentage: float = 10
    min_bid_up_percentage: float = 5


class AuctionHouse(PublicAuctionHouse):
    user_id: str
    created_at: datetime
    wallet: str

    extra: AuctionHouseConfig


class AuctionExtra(BaseModel):
    currency: Optional[str] = None


class CreateAuctionItem(BaseModel):
    name: str
    description: Optional[str] = None
    starting_price: float = 0


class PublicAuctionItem(BaseModel):
    id: str
    auction_house_id: str
    name: str
    active: bool = True
    description: Optional[str] = None
    starting_price: float = 0
    current_price: float = 0
    created_at: datetime
    expires_at: datetime
    bid_count: int = Field(default=0, no_database=True)
    currency: str = Field(default="sat", no_database=True)


class AuctionItem(PublicAuctionItem):
    user_id: str
    extra: AuctionExtra = AuctionExtra()


class AuctionItemFilters(FilterModel):

    name: str | None
    description: str | None
    starting_price: float | None
    current_price: float | None
    created_at: datetime | None
    expires_at: datetime | None
