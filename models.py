from __future__ import annotations

from datetime import datetime
from typing import Optional

from lnbits.db import FilterModel
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis
from pydantic import BaseModel, Field

from .helpers import format_amount, is_ws_url, validate_pub_key


class CustomCost(BaseModel):
    bracket: int
    amount: float

    def validate_data(self):
        assert self.bracket >= 0, "Bracket must be positive."
        assert self.amount >= 0, "Custom cost must be positive."


class PriceData(BaseModel):
    currency: str
    price: float
    discount: float = 0
    referer_bonus: float = 0

    reason: str

    async def price_sats(self) -> float:
        if self.price == 0:
            return 0
        if self.currency == "sats":
            return self.price
        return await fiat_amount_as_satoshis(self.price, self.currency)

    async def discount_sats(self) -> float:
        if self.discount == 0:
            return 0
        if self.currency == "sats":
            return self.discount
        return await fiat_amount_as_satoshis(self.discount, self.currency)

    async def referer_bonus_sats(self) -> float:
        if self.referer_bonus == 0:
            return 0
        if self.currency == "sats":
            return self.referer_bonus
        return await fiat_amount_as_satoshis(self.referer_bonus, self.currency)


class Promotion(BaseModel):
    code: str = ""
    buyer_discount_percent: float
    referer_bonus_percent: float
    selected_referer: Optional[str] = None

    def validate_data(self):
        assert (
            0 <= self.buyer_discount_percent <= 100
        ), f"Discount percent for '{self.code}' must be between 0 and 100."
        assert (
            0 <= self.referer_bonus_percent <= 100
        ), f"Referer percent for '{self.code}' must be between 0 and 100."
        assert self.buyer_discount_percent + self.referer_bonus_percent <= 100, (
            f"Discount and Referer for '{self.code}'" " must be less than 100%."
        )


class PromoCodeStatus(BaseModel):
    buyer_discount: Optional[float] = None
    allow_referer: bool = False
    referer: Optional[str] = None


class RotateAddressData(BaseModel):
    secret: str
    pubkey: str


class UpdateAddressData(BaseModel):
    pubkey: Optional[str] = None
    relays: Optional[list[str]] = None

    def validate_data(self):
        self.validate_relays_urls()
        self.validate_pubkey()

    def validate_relays_urls(self):
        if not self.relays:
            return
        for r in self.relays:
            if not is_ws_url(r):
                raise ValueError(f"Relay '{r}' is not valid!")

    def validate_pubkey(self):
        if self.pubkey and self.pubkey != "":
            self.pubkey = validate_pub_key(self.pubkey)


class CreateAddressData(BaseModel):
    auction_house_id: str
    local_part: str
    pubkey: str = ""
    years: int = 1
    relays: Optional[list[str]] = None
    promo_code: Optional[str] = None
    referer: Optional[str] = None
    create_invoice: bool = False

    def normalize(self):
        self.local_part = self.local_part.strip()
        self.pubkey = self.pubkey.strip()
        if self.relays:
            self.relays = [r.strip() for r in self.relays]

        if self.promo_code:
            self.promo_code = self.promo_code.strip()
            if "@" in self.promo_code:
                elements = self.promo_code.rsplit("@")
                self.promo_code = elements[0]
                self.referer = elements[1]

        if self.referer:
            self.referer = self.referer.strip()


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
    created_at: datetime
    wallet: str

    extra: AuctionHouseConfig


class LnAddressConfig(BaseModel):
    wallet: str
    min: int = 1
    max: int = 10_000_000
    pay_link_id: Optional[str] = ""


class AddressExtra(BaseModel):
    currency: Optional[str] = None
    price: Optional[float] = None
    price_in_sats: Optional[float] = None
    payment_hash: Optional[str] = None
    reimburse_payment_hash: Optional[str] = None
    promo_code: Optional[str] = None
    referer: Optional[str] = None
    activated_by_owner: bool = False
    years: int = 1
    max_years: int = 1
    relays: list[str] = []
    ln_address: LnAddressConfig = LnAddressConfig(wallet="")


class Address(BaseModel):
    id: str
    owner_id: Optional[str] = None
    auction_house_id: str
    local_part: str
    active: bool
    time: datetime
    expires_at: datetime
    pubkey: Optional[str] = None
    reimburse_amount: int = 0
    promo_code_status: PromoCodeStatus = Field(
        default=PromoCodeStatus(), no_database=True
    )
    extra: AddressExtra = AddressExtra()


class AddressStatus(BaseModel):
    identifier: str
    available: bool = False
    price: Optional[float] = None
    price_in_sats: Optional[float] = None
    price_reason: Optional[str] = None
    currency: Optional[str] = None

    @property
    def price_formatted(self) -> str:
        if self.available and self.price and self.currency:
            return format_amount(self.price, self.currency)

        return ""


class AddressFilters(FilterModel):
    auction_house_id: str
    local_part: str
    reimburse_amount: str
    pubkey: str
    active: bool
    time: datetime


class BidsSettings(BaseModel):
    cloudflare_access_token: Optional[str] = None
    lnaddress_api_admin_key: Optional[str] = ""
    lnaddress_api_endpoint: Optional[str] = "https://nostr.com"


class UserSetting(BaseModel):
    owner_id: str
    settings: BidsSettings
