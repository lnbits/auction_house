from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.db import Filters, Page
from lnbits.helpers import urlsafe_short_hash
from loguru import logger

from .crud import (
    create_auction_item,
    create_bid,
    get_auction_item_by_id,
    get_auction_items_paginated,
    get_auction_room_by_id,
    get_auction_rooms,
    get_bid_by_payment_hash,
    get_top_bid,
    update_bid,
    update_top_bid,
)
from .models import (
    AuctionItem,
    AuctionItemFilters,
    AuctionRoom,
    Bid,
    BidRequest,
    BidResponse,
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


async def get_auction_room_items_paginated(
    auction_room: AuctionRoom,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[PublicAuctionItem]:

    page = await get_auction_items_paginated(
        auction_room_id=auction_room.id, filters=filters
    )
    for item in page.data:
        await get_auction_item_details(item)

    return page


async def get_auction_item(item_id: str) -> Optional[PublicAuctionItem]:
    item = await get_auction_item_by_id(item_id)
    if not item:
        return None

    return await get_auction_item_details(item)


async def get_auction_item_details(item: PublicAuctionItem) -> PublicAuctionItem:
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        return item

    top_bid = await get_top_bid(item.id)
    if top_bid:
        item.current_price_sat = top_bid.amount_sat
        item.current_price = top_bid.amount

    time_left = item.expires_at - datetime.now(timezone.utc)
    item.time_left_seconds = max(0, int(time_left.total_seconds()))
    item.currency = auction_room.currency
    if item.time_left_seconds > 0:
        if item.current_price == 0:
            item.next_min_bid = item.starting_price
        else:
            item.next_min_bid = round(
                item.current_price * (1 + auction_room.min_bid_up_percentage / 100), 2
            )

    else:
        item.active = False

    return item


async def place_bid(
    user_id: str, auction_item_id: str, data: BidRequest
) -> BidResponse:
    auction_item = await get_auction_item(auction_item_id)
    if not auction_item:
        raise ValueError("Auction Item not found.")
    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        raise ValueError("Auction Room not found.")
    if auction_item.active is False:
        raise ValueError("Auction Closed.")

    if auction_item.next_min_bid > data.amount:
        raise ValueError(
            f"Bid amount too low. Next min bid: {auction_item.next_min_bid}"
        )

    payment: Payment = await create_invoice(
        wallet_id=auction_room.wallet,
        amount=data.amount,
        currency=auction_room.currency,
        extra={"tag": "auction_house"},
        memo=f"Auction Bid. Item: {auction_room.name}/{auction_item.name}."
        f"Amount: {data.amount} {auction_room.currency}",
    )

    bid = Bid(
        id=urlsafe_short_hash(),
        user_id=user_id,
        auction_item_id=auction_item.id,
        currency=auction_room.currency,
        payment_hash=payment.payment_hash,
        amount=data.amount,
        amount_sat=payment.sat,
        memo=data.memo or "",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await create_bid(bid)
    return BidResponse(
        id=bid.id,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
    )


async def new_bid_made(payment: Payment) -> None:
    bid = await get_bid_by_payment_hash(payment.payment_hash)
    if not bid:
        logger.warning(f"Payment received for unknown bid: {payment.payment_hash}")
        return
    auction_item = await get_auction_item(bid.auction_item_id)
    if not auction_item:
        logger.warning(
            f"Payment received for unknown auction item: {bid.auction_item_id}"
        )
        return
    if not auction_item.active:
        logger.warning(f"Payment received for closed auction: {payment.payment_hash}")
        # TODO: refund payment
        return
    if bid.amount_sat < auction_item.next_min_bid:
        logger.warning(
            f"Payment received for bid too low: {payment.payment_hash}. "
            f"Bid: {bid.amount_sat} Next Min Bid: {auction_item.next_min_bid}. "
            f"Auction Item: '{auction_item.name}' "
            f"({auction_item.auction_room_id}/{auction_item.id})"
        )
        # todo: refund payment
        return
    # todo: more checks
    await _accept_bid(bid, payment.payment_hash)

    logger.debug(f"Bid accepted for '{auction_item.name}' for '{bid.amount_sat} sat'.")


async def _accept_bid(bid: Bid, payment_hash: str):
    bid.paid = True
    bid.payment_hash = payment_hash
    await update_bid(bid)
    await update_top_bid(bid.auction_item_id, bid.id)
