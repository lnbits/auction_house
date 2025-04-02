import json
from datetime import datetime, timezone
from typing import Any, Optional

import bolt11
import httpx
from lnbits.core.crud import get_wallets
from lnbits.core.crud.wallets import create_wallet, delete_wallet_by_id
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.core.services.websockets import websocket_updater
from lnbits.db import Filters, Page
from lnbits.helpers import check_callback_url, urlsafe_short_hash
from loguru import logger

from .crud import (
    close_auction,
    create_auction_item,
    create_audit_entry,
    create_bid,
    get_active_auction_items,
    get_auction_item_by_id,
    get_auction_items_paginated,
    get_auction_room_by_id,
    get_auction_rooms,
    get_bid_by_payment_hash,
    get_top_bid,
    get_user_bidded_items_ids,
    update_auction_item,
    update_auction_item_top_price,
    update_bid,
    update_top_bid,
)
from .models import (
    AuctionItem,
    AuctionItemExtra,
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
    if data.ask_price <= 0:
        message = f"Ask price must be positive. Got {data.ask_price}."
        await db_log(auction_room.id, message)
        raise ValueError(message)
    expires_at = datetime.now(timezone.utc) + auction_room.extra.duration.to_timedelta()
    data.name = data.name.strip()
    # todo: is_valid_email_address
    extra = AuctionItemExtra(
        transfer_code=data.transfer_code,
        owner_ln_address=data.ln_address,
        wallet_id="id_only_after_webhook",
    )
    item = AuctionItem(
        id=urlsafe_short_hash(),
        name=data.name,
        description=data.description,
        ask_price=data.ask_price,
        user_id=user_id,
        auction_room_id=auction_room.id,
        expires_at=expires_at,
        extra=extra,
    )

    wh = auction_room.extra.lock_webhook
    if not wh.url:
        await db_log(item.id, f"No lock webhook for auction room {auction_room.id}.")
    else:
        lock_data = await call_webhook_for_auction_item(
            item.id, wh, placeholders={"transfer_code": data.transfer_code}
        )
        lock_code = lock_data.get("lock_code", None)
        if not lock_code:
            await db_log(item.id, f"Failed to get lock code {item.name} ({item.id}).")
            raise ValueError("Lock Webhook did not return a code.")
        item.extra.lock_code = lock_code
        await db_log(item.id, f"Lock code obtained {item.name} ({item.id}).")

    item_wallet = await create_wallet(
        user_id=auction_room.user_id, wallet_name=f"AH: {item.name}"
    )
    item.extra.wallet_id = item_wallet.id

    await create_auction_item(item)
    await db_log(item.id, f"Added item {item.name} ({item.id}).")
    return item


async def call_webhook_for_auction_item(
    item_id: str, wh: Webhook, placeholders: dict[str, Any]
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        check_callback_url(wh.url)
        res = await client.request(
            wh.method, wh.url, json=wh.data_json(**placeholders), timeout=5
        )
        if res.status_code != 200:
            await db_log(
                item_id,
                f"Webhook failed. "
                f"Expected return code '200' but got '{res.status_code}'.",
            )
            raise ValueError("Webhook failed.")

        return res.json()


async def get_auction_room_items_paginated(
    auction_room: AuctionRoom,
    user_id: Optional[str] = None,
    include_inactive: Optional[bool] = None,
    user_is_owner: Optional[bool] = None,
    user_is_participant: Optional[bool] = None,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[AuctionItem]:
    bidded_items_ids = await get_user_bidded_items_ids(user_id) if user_id else []

    owner_user_id = user_id if user_is_owner else None
    page = await get_auction_items_paginated(
        auction_room_id=auction_room.id,
        include_inactive=include_inactive,
        user_id=owner_user_id,
        auction_item_ids=bidded_items_ids if user_is_participant else None,
        filters=filters,
    )

    for item in page.data:
        await get_auction_item_details(item, user_id, auction_room, bidded_items_ids)

    return page


async def get_auction_item(
    item_id: str,
    user_id: Optional[str] = None,
) -> Optional[AuctionItem]:
    item = await get_auction_item_by_id(item_id)
    if not item:
        return None

    public_item = await get_auction_item_details(item, user_id)
    return AuctionItem(**{**item.dict(), **public_item.dict()})


async def get_auction_item_details(
    item: PublicAuctionItem,
    user_id: Optional[str] = None,
    auction_room: Optional[AuctionRoom] = None,
    bidded_items_ids: Optional[list[str]] = None,
) -> PublicAuctionItem:
    if not auction_room:
        auction_room = await get_auction_room_by_id(item.auction_room_id)

    top_bid = await get_top_bid(item.id)
    if top_bid:
        item.current_price_sat = top_bid.amount_sat
        item.current_price = top_bid.amount
        item.user_is_top_bidder = top_bid.user_id == user_id

    if user_id and bidded_items_ids is None:
        bidded_items_ids = await get_user_bidded_items_ids(user_id)
    if item.id in (bidded_items_ids or []):
        item.user_is_participant = True

    item.time_left_seconds = max(0, int(item.time_left.total_seconds()))

    if not auction_room:
        return item
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
        if item.time_left.total_seconds() > 0:
            continue
        try:
            await close_auction_item(item)
        except Exception as e:
            await db_log(item.id, f"Error closing auction item {item.id}: {e}")


async def close_auction_item(item: AuctionItem):
    await db_log(item.id, f"Closing auction item {item.name} ({item.id}).")
    item.active = False
    await update_auction_item(item)

    top_bid = await get_top_bid(item.id)
    if not top_bid:
        await db_log(item.id, f"No bids for item {item.name} ({item.id}). Unlocking.")
        await unlock_auction_item(item)
    else:
        await transfer_auction_item(item, top_bid.user_id)
        await pay_auction_item(item, top_bid)  # todo; transfer will fail a second time

    await close_auction(item.id)

    if item.extra.is_owner_paid:
        await db_log(
            item.id,
            f"Soft deleted wallet '{item.extra.wallet_id}' "
            f"for  {item.name} ({item.id}).",
        )
        await delete_wallet_by_id(item.extra.wallet_id)

    await db_log(item.id, f"Closed auction item {item.name} ({item.id}).")
    await ws_notify(item.id, {"status": "closed"})


async def pay_auction_item(item: AuctionItem, top_bid: Bid):
    await db_log(item.id, f"Paying fee and owner for {item.name} ({item.id}).")
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        message = f"No auction room found for item {item.name} ({item.id}."
        await db_log(item.id, message)
        raise ValueError(message)

    fee_amount_sat = int(top_bid.amount_sat * auction_room.room_percentage / 100)
    owner_amount_sat = top_bid.amount_sat - fee_amount_sat

    is_fee_paid = await _pay_fee_for_ended_auction(
        item, item.extra.wallet_id, auction_room.fee_wallet_id, fee_amount_sat
    )
    await db_log(item.id, f"Fee paid: {is_fee_paid}. Item {item.name} ({item.id}).")

    is_owner_paid = await _pay_owner_for_ended_auction(
        item, item.extra.wallet_id, owner_amount_sat
    )
    await db_log(item.id, f"Owner paid: {is_owner_paid}. Item {item.name} ({item.id}).")


async def unlock_auction_item(item: AuctionItem):
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        message = f"No auction room found for item {item.name} ({item.id}."
        await db_log(item.id, message)
        raise ValueError(message)

    wh = auction_room.extra.unlock_webhook
    if not wh.url:
        await db_log(item.id, f"No unlock webhook for item {item.name} ({item.id}).")
        return None

    unlock_data = await call_webhook_for_auction_item(
        item.id, wh, placeholders={"lock_code": item.extra.lock_code}
    )
    success = unlock_data.get("success", False)
    if not success:
        await db_log(
            item.id, f"Failed to unlock item {item.name} ({item.id}): {unlock_data}."
        )
        raise ValueError(f"Failed to unlock item {item.name} ({item.id}).")
    return None


async def transfer_auction_item(item: AuctionItem, new_owner_id: str):
    await db_log(item.id, f"Transferring {item.name} ({item.id}).")
    auction_room = await get_auction_room_by_id(item.auction_room_id)
    if not auction_room:
        message = f"No auction room found for item {item.name} ({item.id}."
        await db_log(item.id, message)
        raise ValueError(message)

    wh = auction_room.extra.transfer_webhook
    if not wh.url:
        await db_log(item.id, f"No transfer webhook for item {item.name} ({item.id}).")
        return None

    transfer_data = await call_webhook_for_auction_item(
        item.id,
        wh,
        placeholders={"lock_code": item.extra.lock_code, "new_owner_id": new_owner_id},
    )
    success = transfer_data.get("success", False)
    if not success:
        await db_log(
            item.id, f"Failed to unlock item {item.name} ({item.id}): {transfer_data}."
        )
        raise ValueError(f"Failed to unlock item {item.name} ({item.id}).")
    await db_log(item.id, f"Transfered {item.name} ({item.id}).")


async def place_bid(
    user_id: str, auction_item_id: str, data: BidRequest
) -> BidResponse:
    await db_log(
        auction_item_id, f"Placing bid for item {auction_item_id}. Memo: {data.memo}"
    )
    auction_item = await get_auction_item(auction_item_id, user_id)
    if not auction_item:
        message = f"Auction Item not found for id {auction_item_id}."
        await db_log(auction_item_id, message)
        raise ValueError(message)
    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        message = (
            f"Auction Room not found for item {auction_item.name} ({auction_item.id})."
        )
        await db_log(auction_item_id, message)
        raise ValueError(message)
    if auction_item.active is False:
        message = f"Auction Closed for item {auction_item.name} ({auction_item.id})."
        await db_log(auction_item_id, message)
        raise ValueError(message)

    if auction_item.next_min_bid > data.amount:
        message = f"Bid amount too low. Next min bid: {auction_item.next_min_bid}"
        await db_log(auction_item_id, message)
        raise ValueError(message)

    top_bid = await get_top_bid(auction_item_id)
    if top_bid and top_bid.user_id == user_id:
        message = "You are already the top bidder."
        await db_log(auction_item_id, message)
        raise ValueError(message)

    payment: Payment = await create_invoice(
        wallet_id=auction_item.extra.wallet_id,
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
    )
    await create_bid(bid)
    await db_log(
        auction_item_id, f"Placed bid for item {auction_item_id}. Memo: {data.memo}"
    )
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
    await db_log(bid.auction_item_id, f"Payment received for {bid_details}")
    if bid.amount_sat != payment.sat:
        await db_log(
            bid.auction_item_id,
            "Payment amount different than bid amount. "
            f"Payment amount: {payment.sat}. {bid_details}",
        )
        return False

    auction_item = await get_auction_item(bid.auction_item_id)
    if not auction_item:
        await db_log(
            bid.auction_item_id,
            "Payment received for unknown auction item: "
            f"{bid.auction_item_id}. {bid_details}",
        )
        return False

    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        await db_log(
            auction_item.id,
            f"No auction room found for bid '{bid.memo}' ({bid.id}).",
        )
        return False

    # race condition between two bids
    if await _must_refund_bid_payment(bid, auction_item):
        await db_log(auction_item.id, f"Refunding. {bid_details}")
        refunded = await _refund_payment(bid)
        await db_log(auction_item.id, f"Refunded: {refunded}. {bid_details}")
        return False

    await _refund_previous_winner(auction_item)
    if auction_room.is_auction:
        await _accept_bid(bid)
    elif auction_room.is_fixed_price:
        await _accept_buy(bid)
        await close_auction_item(auction_item)

    await db_log(
        auction_item.id, f"Bid accepted for '{auction_item.name}' {bid_details}"
    )
    await ws_notify(auction_item.id, {"status": "new_bid"})
    await ws_notify(
        auction_room.id, {"status": "new_bid", "auction_item_id": auction_item.id}
    )

    return True


async def db_log(entry_id: str, data: str) -> bool:
    logger.debug(f"[auction_house][{entry_id}]: {data}")
    try:
        await create_audit_entry(entry_id, data)
    except Exception as e:
        logger.warning(f"Failed to log to db: {e}")
        return False
    return True


async def ws_notify(item_id: str, data: dict) -> bool:
    try:
        await websocket_updater(item_id, json.dumps(data))
    except Exception as e:
        await db_log(item_id, f"Failed to notify websocket: {e}")
        return False
    return True


async def _refund_previous_winner(auction_item: PublicAuctionItem):
    await db_log(
        auction_item.id,
        "Refunding previous winner for item"
        f" {auction_item.name} ({auction_item.id}).",
    )
    try:
        top_bid = await get_top_bid(auction_item.id)
        if not top_bid:
            await db_log(
                auction_item.id,
                "First bid. Nothing to refund for item"
                f" '{auction_item.name}' ({auction_item.id}).",
            )
            return
        await db_log(
            auction_item.id,
            f"Refunding previous winner bid '{top_bid.memo}' ({top_bid.id}).",
        )
        refunded = await _refund_payment(top_bid)
        await db_log(
            auction_item.id,
            f"Refunded: {refunded}. Bid '{top_bid.memo}' ({top_bid.id}).",
        )
    except Exception as e:
        await db_log(
            auction_item.id,
            "Failed to refund bid for auction item "
            f"'{auction_item.name}' ({auction_item.id}): {e}",
        )


async def _must_refund_bid_payment(bid: Bid, auction_item: PublicAuctionItem) -> bool:
    if not auction_item.active:
        await db_log(
            auction_item.id,
            f"Payment received for closed auction:  {bid.auction_item_id}"
            f"Bid: {bid.memo} ({bid.id}).",
        )
        return True

    top_bid = await get_top_bid(auction_item.id)
    if top_bid and bid.amount <= top_bid.amount:
        await db_log(
            bid.auction_item_id,
            f"Payment received for bid too low. "
            f"Bid: {bid.memo} ({bid.id}). "
            f"Bid: {bid.amount}. Next Min Bid: {auction_item.next_min_bid}. "
            f"Auction Item: '{auction_item.name}' "
            f"({auction_item.auction_room_id}/{auction_item.id})",
        )
        return True

    return False


async def _refund_payment(bid: Bid) -> bool:
    auction_item = await get_auction_item_by_id(bid.auction_item_id)
    if not auction_item:
        await db_log(
            bid.auction_item_id,
            f"No auction room found for bid '{bid.memo}' ({bid.id}).",
        )
        return False

    refunded = False
    if bid.ln_address:
        refunded = await _refund_payment_to_ln_address(
            bid, auction_item.extra.wallet_id
        )

    if not refunded:
        refunded = await _refund_payment_to_user_wallet(
            bid, auction_item.extra.wallet_id
        )

    return refunded


async def _refund_payment_to_ln_address(bid: Bid, refund_from_wallet: str) -> bool:
    try:
        payment_description = f"Refund. Memo: {bid.memo}. Bid: {bid.id}."
        if not bid.ln_address:
            message = f"Missing Lightning Address. {payment_description}."
            await db_log(bid.auction_item_id, message)
            raise ValueError(message)

        payment_request = await _ln_address_payment_request(
            bid.auction_item_id, bid.ln_address, bid.amount_sat, payment_description
        )
        await pay_invoice(
            wallet_id=refund_from_wallet,
            payment_request=payment_request,
            description=payment_description,
            extra={"tag": "auction_house", "is_refund": True},
        )
        await db_log(
            bid.auction_item_id,
            f"Refund paid to {bid.ln_address}. Bid {bid.memo} ({bid.id}).",
        )
        return True
    except Exception as e:
        await db_log(
            bid.auction_item_id,
            f"Failed to refund bid '{bid.memo}' ({bid.id}) "
            f"Lightning Address {bid.ln_address}: {e}",
        )
        return False


async def _refund_payment_to_user_wallet(bid: Bid, refund_from_wallet: str) -> bool:
    try:
        wallets = await get_wallets(bid.user_id)
        if len(wallets) == 0:
            await db_log(
                bid.auction_item_id, f"No wallet found for bid '{bid.memo}' ({bid.id})."
            )
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
            description=f"Refund. Memo: '{bid.memo}'. Bid: {bid.id}).",
            extra={"tag": "auction_house", "is_refund": True},
        )
        await db_log(
            bid.auction_item_id,
            f"Refund paid to user wallet. Bid {bid.memo} ({bid.id}).",
        )

        return True
    except Exception as e:
        await db_log(
            bid.auction_item_id,
            f"Failed to refund bid '{bid.memo}' ({bid.id}) to user wallet: {e}",
        )
        return False


async def _ln_address_payment_request(
    item_id: str, ln_address: str, amount_sat: int, payment_description: str = ""
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
        if not callback_url:
            message = f"Missing callback URL for {ln_address}."
            await db_log(item_id, message)
            raise ValueError(message)

        check_callback_url(callback_url)

        min_sendable = int(data.get("minSendable") // 1000)
        if not min_sendable:
            message = f"Missing min_sendable for {ln_address}."
            await db_log(item_id, message)
            raise ValueError(message)

        if amount_sat < min_sendable:
            message = (
                f"Amount too low for {ln_address}." f" Min sendable: {min_sendable}"
            )
            await db_log(item_id, message)
            raise ValueError(message)

        max_sendable = int(data.get("maxSendable") // 1000)
        if not max_sendable:
            message = f"Missing max_sendable for {ln_address}."
            await db_log(item_id, message)
            raise ValueError(message)

        if amount_sat > max_sendable:
            message = (
                f"Amount too high for {ln_address}." f" Max sendable: {max_sendable}"
            )
            await db_log(item_id, message)
            raise ValueError(message)

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
    await db_log(bid.auction_item_id, f"Accepting bid {bid.memo} ({bid.id}).")
    bid.paid = True
    await update_bid(bid)
    await update_top_bid(bid.auction_item_id, bid.id)
    await update_auction_item_top_price(bid.auction_item_id, bid.amount)
    await db_log(bid.auction_item_id, f"Acepted bid {bid.memo} ({bid.id}).")


async def _accept_buy(bid: Bid):
    await db_log(bid.auction_item_id, f"Accepting buy {bid.memo} ({bid.id}).")
    bid.paid = True
    await update_bid(bid)
    await db_log(bid.auction_item_id, f"Acepted buy {bid.memo} ({bid.id}).")


async def _pay_fee_for_ended_auction(
    item: AuctionItem, from_wallet_id: str, to_walet_id: str, amount_sat: int
) -> bool:
    await db_log(item.id, f"Paying fee for item {item.name} ({item.id}).")
    try:
        if item.extra.is_fee_paid:
            await db_log(item.id, f"Fee already paid for item {item.name} ({item.id}).")
            return False
        payment: Payment = await create_invoice(
            wallet_id=to_walet_id,
            amount=amount_sat,
            extra={"tag": "auction_house", "is_fee": True},
            memo="Auction room fee."
            f" Item: {item.name} ({item.auction_room_id}/{item.id}).",
        )
        await pay_invoice(
            wallet_id=from_wallet_id,
            payment_request=payment.bolt11,
            description="Auction room fee."
            f" Item: {item.name} ({item.auction_room_id}/{item.id}).",
            extra={"tag": "auction_house", "is_fee": True},
        )
        item.extra.is_fee_paid = True
        await update_auction_item(item)
        await db_log(item.id, f"Fee paid for item {item.name} ({item.id}).")
    except Exception as e:
        await db_log(
            item.id, f"Failed to pay fee for item {item.name} ({item.id}): {e}"
        )
        return False
    return True


async def _pay_owner_for_ended_auction(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
) -> bool:
    await db_log(item.id, f"Paying owner for item {item.name} ({item.id}).")
    if item.extra.is_owner_paid:
        await db_log(item.id, f"Owner already paid for item {item.name} ({item.id}).")
        return False

    try:
        owner_paid = False
        if item.extra.owner_ln_address:
            owner_paid = await _pay_owner_to_ln_address(
                item, from_wallet_id, amount_sat
            )

        if not owner_paid:
            owner_paid = await _pay_owner_to_internal_wallet(
                item, from_wallet_id, amount_sat
            )

        if owner_paid:
            item.extra.is_owner_paid = True
            await update_auction_item(item)
            await db_log(item.id, f"Owner paid for item {item.name} ({item.id}).")
            return True

        await db_log(item.id, f"Owner NOT paid for item  {item.name} ({item.id}).")
    except Exception as e:
        await db_log(
            item.id, f"Failed to pay owner for item {item.name} ({item.id}): {e}"
        )
    return False


async def _pay_owner_to_ln_address(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
) -> bool:
    try:
        await db_log(
            item.id,
            f"Paying owner to LN address {item.extra.owner_ln_address} "
            f"for item {item.name} ({item.id}).",
        )
        if not item.extra.owner_ln_address:
            message = "Missing Lightning Address."
            await db_log(item.id, message)
            raise ValueError(message)

        payment_request = await _ln_address_payment_request(
            item.id,
            item.extra.owner_ln_address,
            amount_sat,
            f"Payment for {item.name} ({item.id}).",
        )
        await pay_invoice(
            wallet_id=from_wallet_id,
            payment_request=payment_request,
            description=f"Payment to owner {item.extra.owner_ln_address}"
            f" for {item.name} ({item.id}).",
            extra={"tag": "auction_house", "is_owner_payment": True},
        )
        await db_log(
            item.id,
            f"Paid owner to LN address {item.extra.owner_ln_address}"
            f" for item  {item.name} ({item.id}).",
        )
    except Exception as e:
        await db_log(
            item.id,
            f"Failed to pay owner to ln address {item.extra.owner_ln_address} "
            f"for item {item.name} ({item.id}): {e}",
        )
        return False
    return True


async def _pay_owner_to_internal_wallet(
    item: AuctionItem, from_wallet_id: str, amount_sat: int
):
    try:
        await db_log(
            item.id,
            f"Paying owner to internal wallet for item {item.name} ({item.id}).",
        )
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
        await db_log(
            item.id,
            "Paid owner to internal wallet" f"for item {item.name} ({item.id}).",
        )
        return True
    except Exception as e:
        await db_log(
            item.id, f"Failed to pay owner for item {item.name} ({item.id}): {e}"
        )
    return False
