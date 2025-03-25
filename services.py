from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bolt11
import httpx
from lnbits.core.crud import get_wallets
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.db import Filters, Page
from lnbits.helpers import check_callback_url, urlsafe_short_hash
from loguru import logger

from .crud import (
    close_auction,
    create_auction_item,
    create_bid,
    get_active_auction_items,
    get_auction_item_by_id,
    get_auction_items_paginated,
    get_auction_room_by_id,
    get_auction_rooms,
    get_bid_by_payment_hash,
    get_top_bid,
    update_auction_item,
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
    Webhook,
)


async def get_user_auction_rooms(user_id: str) -> list[AuctionRoom]:
    return await get_auction_rooms(user_id)


async def add_auction_item(
    auction_room: AuctionRoom, user_id: str, data: CreateAuctionItem
) -> AuctionItem:
    assert data.ask_price > 0, "Ask price must be positive."
    expires_at = datetime.now(timezone.utc) + auction_room.extra.duration.to_timedelta()
    data.name = data.name.strip()
    item = AuctionItem(
        id=urlsafe_short_hash(),
        user_id=user_id,
        auction_room_id=auction_room.id,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        **data.dict(),
    )
    item.extra.owner_ln_address = data.ln_address  # todo: is_valid_email_address

    wh = auction_room.extra.lock_webhook
    if not wh.url:
        logger.warning(f"No lock webhook for auction room {auction_room.id}.")
    else:
        lock_data = await call_webhook_for_auction_item(
            wh, placeholders={"transfer_code": data.transfer_code}
        )
        lock_code = lock_data.get("lock_code", None)
        if not lock_code:
            raise ValueError("Lock Webhook did not return a code.")
        item.extra.lock_code = lock_code

    await create_auction_item(item)
    return item


async def call_webhook_for_auction_item(
    wh: Webhook, placeholders: dict[str, Any]
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        check_callback_url(wh.url)
        res = await client.request(
            wh.method, wh.url, json=wh.data_json(**placeholders), timeout=5
        )
        if res.status_code != 200:
            logger.warning(
                f"Webhook failed. "
                f"Expected return code '200' but got '{res.status_code}'."
            )
            raise ValueError("Webhook failed.")

        return res.json()


async def get_auction_room_items_paginated(
    auction_room: AuctionRoom,
    user_id: Optional[str] = None,
    include_inactive: Optional[bool] = None,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[AuctionItem]:
    page = await get_auction_items_paginated(
        auction_room_id=auction_room.id,
        include_inactive=include_inactive,
        user_id=user_id,
        filters=filters,
    )
    for item in page.data:
        await get_auction_item_details(item)

    return page


async def get_auction_item(
    item_id: str,
) -> Optional[AuctionItem]:
    item = await get_auction_item_by_id(item_id)
    if not item:
        return None

    public_item = await get_auction_item_details(item)
    return AuctionItem(**{**item.dict(), **public_item.dict()})


async def get_auction_item_details(item: PublicAuctionItem) -> PublicAuctionItem:
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        return item

    top_bid = await get_top_bid(item.id)
    if top_bid:
        item.current_price_sat = top_bid.amount_sat
        item.current_price = top_bid.amount

    time_left = item.expires_at.astimezone(timezone.utc) - datetime.now(timezone.utc)
    item.time_left_seconds = max(0, int(time_left.total_seconds()))
    item.currency = auction_room.currency
    if item.time_left_seconds > 0:
        if item.current_price == 0:
            item.next_min_bid = round(item.ask_price, 2)
        else:
            item.next_min_bid = round(
                item.current_price * (1 + auction_room.min_bid_up_percentage / 100), 2
            )

    else:
        item.active = False

    return item


async def checked_expired_auctions():
    auction_items = await get_active_auction_items()
    for item in auction_items:
        time_left = item.expires_at.astimezone(timezone.utc) - datetime.now(
            timezone.utc
        )
        if time_left.total_seconds() > 0:
            continue
        try:
            await close_auction_item(item)
        except Exception as e:
            logger.error(f"Error closing auction item {item.id}: {e}")


async def close_auction_item(item: AuctionItem):
    logger.info(f"Closing auction item {item.name} ({item.id}).")
    item.active = False
    await update_auction_item(item)

    top_bid = await get_top_bid(item.id)
    if not top_bid:
        logger.info(f"No bids for item {item.name} ({item.id}). Unlocking.")
        await unlock_auction_item(item)
    else:
        logger.info(f"Preparing to transfer {item.name} ({item.id}).")
        await transfer_auction_item(item, top_bid.user_id)
        await pay_auction_item(item, top_bid)

    await close_auction(item.id)

    return None


async def pay_auction_item(item: AuctionItem, top_bid: Bid):
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        raise ValueError(f"No auction room found for item {item.name} ({item.id}.")

    to_walet_id = auction_room.fee_wallet_id or auction_room.wallet_id
    fee_amount_sat = int(top_bid.amount_sat * auction_room.room_percentage / 100)
    owner_amount_sat = top_bid.amount_sat - fee_amount_sat

    is_fee_paid = await _pay_fee_for_ended_auction(
        item, auction_room.wallet_id, to_walet_id, fee_amount_sat
    )
    logger.info(f"Fee paid: {is_fee_paid}. Item {item.name} ({item.id}).")

    is_owner_paid = await _pay_owner_for_ended_auction(
        item, auction_room.wallet_id, owner_amount_sat
    )
    logger.info(f"Owner paid: {is_owner_paid}. Item {item.name} ({item.id}).")


async def _pay_fee_for_ended_auction(
    item: AuctionItem, from_wallet_id: str, to_walet_id: str, amount_sat: int
) -> bool:
    try:
        if item.extra.is_fee_paid:
            logger.info(f"Fee already paid for item {item.name} ({item.id}).")
            return False
        payment: Payment = await create_invoice(
            wallet_id=to_walet_id,
            amount=amount_sat,
            extra={"tag": "auction_house", "is_fee": True},
            memo=f"Fee Payment. Item: {item.name} ({item.auction_room_id}/{item.id}).",
        )
        await pay_invoice(
            wallet_id=from_wallet_id,
            payment_request=payment.bolt11,
            description=f"Fee Payment. Item: {item.name} ({item.auction_room_id}/{item.id}).",
            extra={"tag": "auction_house", "is_fee": True},
        )
        item.extra.is_fee_paid = True
        await update_auction_item(item)
    except Exception as e:
        logger.warning(f"Failed to pay fee for item {item.name} ({item.id}): {e}")
        return False
    return True


async def _pay_owner_for_ended_auction(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
) -> bool:
    if item.extra.is_owner_paid:
        logger.info(f"Owner already paid for item {item.name} ({item.id}).")
        return False

    try:
        owner_paid = False
        if item.extra.owner_ln_address:
            owner_paid = await _pay_owner_to_ln_address(
                item, from_wallet_id, amount_sat
            )

        if not owner_paid:
            owner_paid = await _pay_owner_to_internal_address(
                item, from_wallet_id, amount_sat
            )

        if owner_paid:
            item.extra.is_owner_paid = True
            await update_auction_item(item)
    except Exception as e:
        logger.warning(f"Failed to pay owner for item {item.name} ({item.id}): {e}")
        return False
    return True


async def _pay_owner_to_ln_address(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
) -> bool:
    try:
        assert item.extra.owner_ln_address, "Missing Lightning Address."
        payment_request = await _ln_address_payment_request(
            item.extra.owner_ln_address,
            amount_sat,
            f"Payment for {item.name} ({item.id}).",
        )
        await pay_invoice(
            wallet_id=from_wallet_id,
            payment_request=payment_request,
            description=f"Payment to {item.extra.owner_ln_address}"
            f" for owner of {item.name} ({item.id}).",
            extra={"tag": "auction_house", "is_owner_payment": True},
        )
    except Exception as e:
        logger.warning(
            f"Failed to pay owner to ln address {item.extra.owner_ln_address} "
            f"for item {item.name} ({item.id}): {e}"
        )
        return False
    return True


async def _pay_owner_to_internal_address(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
):
    try:
        wallets = await get_wallets(item.user_id)
        if len(wallets) == 0:
            raise ValueError(f"No wallet found for user {item.user_id}.")
        user_wallet = wallets[0]
        payment: Payment = await create_invoice(
            wallet_id=user_wallet.id,
            amount=amount_sat,
            extra={"tag": "auction_house", "is_owner_payment": True},
            memo=f"Payment for {item.name} ({item.id}).",
        )
        await pay_invoice(
            wallet_id=from_wallet_id,
            payment_request=payment.bolt11,
            description=f"Payment to user wallet for owner of {item.name} ({item.id}).",
            extra={"tag": "auction_house", "is_owner_payment": True},
        )
    except Exception as e:
        logger.warning(f"Failed to pay owner for item {item.name} ({item.id}): {e}")
        return False


async def unlock_auction_item(item: AuctionItem):
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        raise ValueError(f"No auction room found for item {item.name} ({item.id}.")

    wh = auction_room.extra.lock_webhook
    if not wh.url:
        logger.warning(f"No unlock webhook for item {item.name} ({item.id}).")
        return None

    unlock_data = await call_webhook_for_auction_item(
        wh, placeholders={"lock_code": item.extra.lock_code}
    )
    success = unlock_data.get("success", False)
    if not success:
        logger.warning(f"Failed to unlock item {item.name} ({item.id}): {unlock_data}.")
        raise ValueError(f"Failed to unlock item {item.name} ({item.id}).")
    return None


async def transfer_auction_item(item: AuctionItem, new_owner_id: str):
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        raise ValueError(f"No auction room found for item {item.name} ({item.id}.")

    wh = auction_room.extra.transfer_webhook
    if not wh.url:
        logger.warning(f"No transfer webhook for item {item.name} ({item.id}).")
        return None

    transfer_data = await call_webhook_for_auction_item(
        wh,
        placeholders={"lock_code": item.extra.lock_code, "new_owner_id": new_owner_id},
    )
    success = transfer_data.get("success", False)
    if not success:
        logger.warning(
            f"Failed to unlock item {item.name} ({item.id}): {transfer_data}."
        )
        raise ValueError(f"Failed to unlock item {item.name} ({item.id}).")
    return None


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

    top_bid = await get_top_bid(auction_item_id)
    if top_bid and top_bid.user_id == user_id:
        raise ValueError("You are already the top bidder.")

    payment: Payment = await create_invoice(
        wallet_id=auction_room.wallet_id,
        amount=data.amount,
        currency=auction_room.currency,
        extra={"tag": "auction_house"},
        memo=f"Auction Bid. Item: {auction_room.name}/{auction_item.name}. "
        f"Amount: {data.amount} {auction_room.currency}",
    )
    currency = auction_room.currency
    bid = Bid(
        id=urlsafe_short_hash(),
        user_id=user_id,
        auction_item_id=auction_item.id,
        currency=currency,
        payment_hash=payment.payment_hash,
        amount=data.amount,
        amount_sat=payment.sat,
        memo=data.memo[:200],
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
        # todo: refund bid if possible
        return False

    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        logger.warning(f"No auction room found for bid '{bid.memo}' ({bid.id}).")
        return False

    # race condition between two bids
    if await _must_refund_bid_payment(bid, auction_item):
        logger.info(f"Refunding. {bid_details}")
        refunded = await _refund_payment(bid, auction_item.auction_room_id)
        logger.info(f"Refunded: {refunded}. {bid_details}")
        return False

    await _refund_previous_winner(auction_item)
    if auction_room.is_auction:
        await _accept_bid(bid)
    elif auction_room.is_fixed_price:
        await _accept_buy(bid)
        await close_auction_item(auction_item)

    logger.debug(f"Bid accepted for '{auction_item.name}' {bid_details}")

    return True


async def _refund_previous_winner(auction_item: PublicAuctionItem):
    try:
        top_bid = await get_top_bid(auction_item.id)
        if not top_bid:
            logger.info(
                "First bid. "
                f"Nothing to refund for item '{auction_item.name}' ({auction_item.id})."
            )
            return
        logger.info(f"Refunding previous winner bid '{top_bid.memo}' ({top_bid.id}).")
        refunded = await _refund_payment(top_bid, auction_item.auction_room_id)
        logger.info(f"Refunded: {refunded}. Bid '{top_bid.memo}' ({top_bid.id}).")
    except Exception as e:
        logger.warning(
            "Failed to refund bid for auction item "
            f"'{auction_item.name}' ({auction_item.id}): {e}"
        )


async def _must_refund_bid_payment(bid: Bid, auction_item: PublicAuctionItem) -> bool:
    if not auction_item.active:
        logger.warning(
            f"Payment received for closed auction:  {bid.auction_item_id}"
            f"Bid: {bid.memo} ({bid.id})."
        )
        return True

    top_bid = await get_top_bid(auction_item.id)
    if top_bid and bid.amount <= top_bid.amount:
        logger.warning(
            f"Payment received for bid too low. "
            f"Bid: {bid.memo} ({bid.id}). "
            f"Bid: {bid.amount}. Next Min Bid: {auction_item.next_min_bid}. "
            f"Auction Item: '{auction_item.name}' "
            f"({auction_item.auction_room_id}/{auction_item.id})"
        )
        return True

    return False


async def _refund_payment(bid: Bid, auction_room_id: str) -> bool:
    auction_room = await get_auction_room_by_id(auction_room_id)
    if not auction_room:
        logger.warning(f"No auction room found for bid '{bid.memo}' ({bid.id}).")
        return False

    refunded = False
    if bid.ln_address:
        refunded = await _refund_payment_to_ln_address(bid, auction_room.wallet_id)

    if not refunded:
        refunded = await _refund_payment_to_user_wallet(bid, auction_room.wallet_id)

    return refunded


async def _refund_payment_to_ln_address(bid: Bid, refund_from_wallet: str) -> bool:
    try:
        payment_description = f"Refund for {bid.memo} ({bid.auction_item_id}/{bid.id})."
        assert bid.ln_address, f"Missing Lightning Address. {payment_description}."
        payment_request = await _ln_address_payment_request(
            bid.ln_address, bid.amount_sat, payment_description
        )
        await pay_invoice(
            wallet_id=refund_from_wallet,
            payment_request=payment_request,
            description=payment_description,
            extra={"tag": "auction_house", "is_refund": True},
        )
        logger.info(f"Refund paid to {bid.ln_address}. Bid {bid.memo} ({bid.id}).")
        return True
    except Exception as e:
        logger.warning(
            f"Failed to refund bid '{bid.memo}' ({bid.id}) "
            f"Lightning Address {bid.ln_address}: {e}"
        )
        return False


async def _refund_payment_to_user_wallet(bid: Bid, refund_from_wallet: str) -> bool:
    try:
        wallets = await get_wallets(bid.user_id)
        if len(wallets) == 0:
            logger.warning(f"No wallet found for bid '{bid.memo}' ({bid.id}).")
            return False

        user_wallet = wallets[0]

        refund_payment: Payment = await create_invoice(
            wallet_id=user_wallet.id,
            amount=bid.amount_sat,
            extra={"tag": "auction_house", "is_refund": True},
            memo=f"Refund amount: {bid.amount} {bid.currency} ({bid.amount_sat} sat). "
            f"Bid: {bid.memo} ({bid.id}).",
        )

        await pay_invoice(
            wallet_id=refund_from_wallet,
            payment_request=refund_payment.bolt11,
            description=f"Refund for {bid.memo} ({bid.id}).",
            extra={"tag": "auction_house", "is_refund": True},
        )
        logger.info(f"Refund paid to user wallet. Bid {bid.memo} ({bid.id}).")

        return True
    except Exception as e:
        logger.warning(
            f"Failed to refund bid '{bid.memo}' ({bid.id}) to user wallet: {e}"
        )
        return False


async def _ln_address_payment_request(
    ln_address: str, amount_sat: int, payment_description: str = ""
) -> str:
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
        callback_url = data.get("callback")
        assert callback_url, f"Missing callback URL for {ln_address}."
        check_callback_url(callback_url)

        min_sendable = int(data.get("minSendable") // 1000)
        assert min_sendable, f"Missing min_sendable for {ln_address}."
        assert min_sendable <= amount_sat, (
            f"Amount too low for {ln_address}." f" Min sendable: {min_sendable}"
        )

        max_sendable = int(data.get("maxSendable") // 1000)
        assert max_sendable, f"Missing max_sendable for {ln_address}."
        assert max_sendable >= amount_sat, (
            f"Amount too high for {ln_address}." f" Max sendable: {max_sendable}"
        )

        amount_msat = amount_sat * 1000
        r = await client.get(
            callback_url,
            params={
                "amount": amount_msat,
                "comment": payment_description,
            },
            timeout=5,
        )
        r.raise_for_status()

        data = r.json()
        if not data.get("pr"):
            raise ValueError(
                f"Missing payment request in callback response for {ln_address}."
            )
        invoice = bolt11.decode(data["pr"])
        if invoice.amount_msat != amount_msat:
            raise ValueError(
                "Amount mismatch in invoice for"
                f" {ln_address} ({payment_description})."
            )

    return data["pr"]


async def _accept_bid(bid: Bid):
    # todo: should be try-catch?
    bid.paid = True
    await update_bid(bid)
    await update_top_bid(bid.auction_item_id, bid.id)
    await update_auction_item_top_price(bid.auction_item_id, bid.amount)


async def _accept_buy(bid: Bid):
    bid.paid = True
    await update_bid(bid)
