from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from lnbits.core.crud import get_wallets
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.db import Filters, Page
from lnbits.helpers import check_callback_url, urlsafe_short_hash
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
    update_auction_item_top_price,
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
    data.name = data.name.strip()
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
        memo=f"Auction Bid. Item: {auction_room.name}/{auction_item.name}. "
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
        ln_address=data.ln_address,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await create_bid(bid)
    return BidResponse(
        id=bid.id,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
    )


async def new_bid_made(payment: Payment) -> bool:
    bid = await get_bid_by_payment_hash(payment.payment_hash)
    if not bid:
        logger.warning(f"Payment received for unknown bid: {payment.payment_hash}")
        return False
    bid_details = (
        f"Bid {bid.memo} ({bid.id}). "
        f"Amount: {bid.amount_sat} sat. {bid.amount} {bid.currency}. "
        f"Payment: {payment.payment_hash}."
    )
    if bid.amount_sat != payment.sat:
        logger.warning(
            "Payment amount different than bid amount. "
            f"Payment amount: {payment.sat}. {bid_details}"
        )
        return False

    auction_item = await get_auction_item(bid.auction_item_id)
    if not auction_item:
        logger.warning(
            "Payment received for unknown auction item: "
            f"{bid.auction_item_id}. {bid_details}"
        )
        return False

    if await _must_refund_bid_payment(bid, auction_item):
        logger.info(f"Refunding. {bid_details}")
        refunded = await _refund_payment(bid, auction_item)
        logger.info(f"Refunded: {refunded}. {bid_details}")
        return True

    assert auction_item

    # todo: more checks
    await _accept_bid(bid)

    logger.debug(f"Bid accepted for '{auction_item.name}' {bid_details}")

    return True


async def _must_refund_bid_payment(bid: Bid, auction_item: PublicAuctionItem) -> bool:

    if not auction_item.active:
        logger.warning(
            f"Payment received for closed auction:  {bid.auction_item_id}"
            f"Bid: {bid.memo} ({bid.id})."
        )
        return True

    if bid.amount < auction_item.next_min_bid:
        logger.warning(
            f"Payment received for bid too low. "
            f"Bid: {bid.memo} ({bid.id}). "
            f"Bid: {bid.amount}. Next Min Bid: {auction_item.next_min_bid}. "
            f"Auction Item: '{auction_item.name}' "
            f"({auction_item.auction_room_id}/{auction_item.id})"
        )
        return True

    return False


async def _refund_payment(bid: Bid, auction_item: PublicAuctionItem) -> bool:
    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        logger.warning(f"No auction room found for bid '{bid.memo}' ({bid.id}).")
        return False

    if bid.ln_address:
        print("### refund to ln address")
        # if success return True

    # todo: extract refund to user wallet
    wallets = await get_wallets(bid.user_id)
    if len(wallets) == 0:
        logger.warning(f"No wallet found for bid '{bid.memo}' ({bid.id}).")
        return False

    user_wallet = wallets[0]

    memo = (
        f"Refund amount: {bid.amount} {bid.currency} ({bid.amount_sat} sat). "
        f"Auction item: '{auction_room.name}/{auction_item.name}'. "
        f"Memo: {bid.memo}. "
        f"Id: {bid.id}."
    )
    refund_payment: Payment = await create_invoice(
        wallet_id=user_wallet.id,
        amount=bid.amount_sat,
        extra={"tag": "auction_house", "is_refund": True},
        memo=memo,
    )

    await pay_invoice(
        wallet_id=auction_room.wallet,
        payment_request=refund_payment.bolt11,
        extra={"tag": "auction_house", "is_refund": True},
    )
    logger.info(f"Refund paid. {memo}")
    return True


async def _fetch_ln_address_invoice(ln_address: str) -> str:
    name_domain = ln_address.split("@")
    if len(name_domain) != 2 and len(name_domain[1].split(".")) < 2:
        raise ValueError(f"Invalid Lightning Address '{ln_address}'.")

    name, domain = name_domain
    url = f"https://{domain}/.well-known/lnurlp/{name}"
    check_callback_url(url)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(url, timeout=5)
        r.raise_for_status()

        data = r.json()
        print("#### data", data)


async def _accept_bid(bid: Bid):
    bid.paid = True
    await update_bid(bid)
    # todo: refund previous top bid
    await update_top_bid(bid.auction_item_id, bid.id)
    await update_auction_item_top_price(bid.auction_item_id, bid.amount)
