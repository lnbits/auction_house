from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.db import Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .crud import (
    create_auction_item,
    get_auction_houses,
    get_auction_items_paginated,
)
from .models import (
    AuctionHouse,
    AuctionItem,
    AuctionItemFilters,
    CreateAuctionItem,
    PublicAuctionItem,
)


async def get_user_auction_houses(user_id: str) -> list[AuctionHouse]:
    return await get_auction_houses(user_id)


async def add_auction_item(
    auction_house: AuctionHouse, user_id: str, data: CreateAuctionItem
) -> PublicAuctionItem:
    assert data.starting_price > 0, "Starting price must be positive."
    expires_at = datetime.now(timezone.utc) + timedelta(days=auction_house.days)
    item = AuctionItem(
        id=urlsafe_short_hash(),
        user_id=user_id,
        auction_house_id=auction_house.id,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        **data.dict(),
    )
    return await create_auction_item(item)


async def get_auction_house_items_paginated(
    auction_house: AuctionHouse,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[PublicAuctionItem]:

    page = await get_auction_items_paginated(
        auction_house_id=auction_house.id, filters=filters
    )
    for item in page.data:
        item.currency = auction_house.currency

    return page
