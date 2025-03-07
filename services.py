from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.db import Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .crud import (
    create_auction_item,
    get_auction_item_by_id,
    get_auction_items_paginated,
    get_auction_room_by_id,
    get_auction_rooms,
)
from .models import (
    AuctionItem,
    AuctionItemFilters,
    AuctionRoom,
    CreateAuctionItem,
    PublicAuctionItem,
)


async def get_user_auction_rooms(user_id: str) -> list[AuctionRoom]:
    return await get_auction_rooms(user_id)


async def add_auction_item(
    auction_room: AuctionRoom, user_id: str, data: CreateAuctionItem
) -> PublicAuctionItem:
    assert data.starting_price > 0, "Starting price must be positive."
    expires_at = datetime.now(timezone.utc) + timedelta(days=auction_room.days)
    item = AuctionItem(
        id=urlsafe_short_hash(),
        user_id=user_id,
        auction_room_id=auction_room.id,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        **data.dict(),
    )
    return await create_auction_item(item)


async def get_auction_item(item_id: str) -> Optional[PublicAuctionItem]:
    item = await get_auction_item_by_id(item_id)
    if not item:
        return None

    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        return None

    time_left = item.expires_at - datetime.now(timezone.utc)
    item.time_left_seconds = max(0, int(time_left.total_seconds()))
    item.currency = auction_room.currency
    if item.time_left_seconds > 0:
        if item.current_price == 0:
            item.next_min_bid = 1
        else:
            item.next_min_bid = int(
                item.current_price * (1 + auction_room.min_bid_up_percentage / 100)
            )
    return item


async def get_auction_room_items_paginated(
    auction_room: AuctionRoom,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[PublicAuctionItem]:

    page = await get_auction_items_paginated(
        auction_room_id=auction_room.id, filters=filters
    )
    for item in page.data:
        item.currency = auction_room.currency

    return page
