from typing import Optional

from lnbits.core.crud import get_user
from lnbits.db import Filters, Page

from .crud import (
    get_all_addresses,
    get_all_addresses_paginated,
    get_auction_houses,
)
from .helpers import (
    normalize_identifier,
    validate_pub_key,
)
from .models import (
    AddressFilters,
    AuctionHouse,
    AuctionItem,
    CreateAddressData,
)


async def get_user_auction_houses(user_id: str) -> list[AuctionHouse]:

    return await get_auction_houses(user_id)


async def get_user_addresses(
    user_id: str, wallet_id: str, all_wallets: Optional[bool] = False
) -> list[AuctionItem]:
    wallet_ids = [wallet_id]
    if all_wallets:
        user = await get_user(user_id)  # type: ignore
        if not user:
            return []
        wallet_ids = user.wallet_ids

    return await get_all_addresses(wallet_ids)


async def get_user_addresses_paginated(
    user_id: str,
    wallet_id: str,
    all_wallets: Optional[bool] = False,
    filters: Optional[Filters[AddressFilters]] = None,
) -> Page[AuctionItem]:
    wallet_ids = [wallet_id]
    if all_wallets:
        user = await get_user(user_id)  # type: ignore
        if not user:
            return Page(data=[], total=0)
        wallet_ids = user.wallet_ids

    return await get_all_addresses_paginated(wallet_ids, filters)


async def create_address(
    auction_house: AuctionHouse,
    data: CreateAddressData,
    wallet_id: Optional[str] = None,
    user_id: Optional[str] = None,
    promo_code: Optional[str] = None,
):

    identifier = normalize_identifier(data.local_part)
    data.local_part = identifier
    if data.pubkey != "":
        data.pubkey = validate_pub_key(data.pubkey)
