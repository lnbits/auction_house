from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.core.crud import get_standalone_payment, get_user
from lnbits.db import Filters, Page
from loguru import logger

from .crud import (
    get_address,
    get_all_addresses,
    get_all_addresses_paginated,
    get_auction_houses,
    update_address,
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


async def activate_address(
    auction_house_id: str, address_id: str, payment_hash: Optional[str] = None
) -> AuctionItem:
    logger.info(f"Activating NIP-05 '{address_id}' for {auction_house_id}")

    address = await get_address(auction_house_id, address_id)
    assert address, f"Cannot find address '{address_id}' for {auction_house_id}."

    address.extra.activated_by_owner = payment_hash is None
    address.extra.payment_hash = payment_hash
    address.active = True
    address.expires_at = datetime.now(timezone.utc) + timedelta(
        days=365 * address.extra.years
    )
    await update_address(address)

    return address


async def check_address_payment(auction_house_id: str, payment_hash: str) -> bool:
    payment = await get_standalone_payment(payment_hash, incoming=True)
    if not payment:
        logger.debug(f"No payment found for hash {payment_hash}")
        return False

    assert payment.extra, "No extra data on payment."
    payment_address_id = payment.extra.get("address_id")
    assert payment_address_id, "Payment does not exist for this address."

    payment_auction_house_id = payment.extra.get("auction_house_id")
    assert (
        payment_auction_house_id == auction_house_id
    ), "Payment does not exist for this auction_house."

    if payment.pending is False:
        return True

    status = await payment.check_status()
    return status.success


async def get_reimburse_wallet_id(address: AuctionItem) -> str:
    payment_hash = address.extra.reimburse_payment_hash
    assert payment_hash, f"No payment hash found to reimburse '{address.id}'."

    payment = await get_standalone_payment(
        checking_id_or_hash=payment_hash, incoming=True
    )
    assert payment, f"No payment found to reimburse '{payment_hash}'."
    assert payment.extra, "No extra data on payment."
    wallet_id = payment.extra.get("reimburse_wallet_id")
    assert wallet_id, f"No wallet found to reimburse payment {payment_hash}."
    return wallet_id
