from datetime import datetime, timedelta, timezone
from typing import Optional

from lnbits.core.crud import get_standalone_payment, get_user
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.db import Filters, Page
from loguru import logger

from .crud import (
    create_address_internal,
    get_active_address_by_local_part,
    get_address,
    get_address_for_owner,
    get_addresses_for_owner,
    get_all_addresses,
    get_all_addresses_paginated,
    get_auction_house_by_id,
    get_auction_houses,
    update_address,
)
from .helpers import (
    normalize_identifier,
    owner_id_from_user_id,
    validate_pub_key,
)
from .models import (
    Address,
    AddressExtra,
    AddressFilters,
    AddressStatus,
    AuctionHouse,
    CreateAddressData,
    PriceData,
)


async def get_user_auction_houses(
    user_id: str, wallet_id: str, all_wallets: Optional[bool] = False
) -> list[AuctionHouse]:
    wallet_ids = [wallet_id]
    if all_wallets:
        user = await get_user(user_id)  # type: ignore
        if not user:
            return []
        wallet_ids = user.wallet_ids

    return await get_auction_houses(wallet_ids)


async def get_user_addresses(
    user_id: str, wallet_id: str, all_wallets: Optional[bool] = False
) -> list[Address]:
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
) -> Page[Address]:
    wallet_ids = [wallet_id]
    if all_wallets:
        user = await get_user(user_id)  # type: ignore
        if not user:
            return Page(data=[], total=0)
        wallet_ids = user.wallet_ids

    return await get_all_addresses_paginated(wallet_ids, filters)


async def get_identifier_status(
    auction_house: AuctionHouse,
    identifier: str,
    years: int,
    promo_code: Optional[str] = None,
) -> AddressStatus:
    identifier = normalize_identifier(identifier)
    address = await get_active_address_by_local_part(auction_house.id, identifier)
    if address:
        return AddressStatus(identifier=identifier, available=False)

    price_data = await get_identifier_price_data(
        auction_house, identifier, years, promo_code
    )

    if not price_data:
        return AddressStatus(identifier=identifier, available=False)

    return AddressStatus(
        identifier=identifier,
        available=True,
        price=price_data.price,
        price_in_sats=await price_data.price_sats(),
        price_reason=price_data.reason,
        currency=auction_house.currency,
    )


async def get_identifier_price_data(
    auction_house: AuctionHouse,
    identifier: str,
    years: int,
    promo_code: Optional[str] = None,
) -> Optional[PriceData]:

    return None


async def create_invoice_for_identifier(
    auction_house: AuctionHouse,
    address: Address,
    reimburse_wallet_id: str,
) -> Payment:
    price_data = await get_identifier_price_data(
        auction_house, address.local_part, address.extra.years, address.extra.promo_code
    )
    assert price_data, f"Cannot compute price for '{address.local_part}'."
    price_in_sats = await price_data.price_sats()
    discount_sats = await price_data.discount_sats()
    referer_bonus_sats = await price_data.referer_bonus_sats()

    payment = await create_invoice(
        wallet_id=auction_house.wallet,
        amount=int(price_in_sats),
        memo=f"Payment  " f"for NIP-05 {address.local_part}",
        extra={
            "tag": "bids",
            "auction_house_id": auction_house.id,
            "address_id": address.id,
            "action": "activate",
            "reimburse_wallet_id": reimburse_wallet_id,
            "discount_sats": int(discount_sats),
            "referer": address.extra.referer,
            "referer_bonus_sats": int(referer_bonus_sats),
        },
    )
    return payment


async def create_address(
    auction_house: AuctionHouse,
    data: CreateAddressData,
    wallet_id: Optional[str] = None,
    user_id: Optional[str] = None,
    promo_code: Optional[str] = None,
) -> Address:

    identifier = normalize_identifier(data.local_part)
    data.local_part = identifier
    if data.pubkey != "":
        data.pubkey = validate_pub_key(data.pubkey)

    owner_id = owner_id_from_user_id(user_id)
    address = await get_address_for_owner(owner_id, auction_house.id, identifier)

    promo_code = promo_code or (address.extra.promo_code if address else None)
    identifier_status = await get_identifier_status(
        auction_house, identifier, data.years, promo_code
    )

    assert identifier_status.available, f"Identifier '{identifier}' not available."
    assert identifier_status.price, f"Cannot compute price for '{identifier}'."

    extra = address.extra if address else AddressExtra()
    extra.price = identifier_status.price
    extra.price_in_sats = identifier_status.price_in_sats
    extra.currency = auction_house.currency
    extra.years = data.years
    extra.promo_code = data.promo_code

    if address:
        assert not address.active, f"Identifier '{data.local_part}' already activated."
        address.extra = extra
        address.pubkey = data.pubkey
        address = await update_address(address)
    else:
        address = await create_address_internal(data, owner_id, extra=extra)

    return address


async def activate_address(
    auction_house_id: str, address_id: str, payment_hash: Optional[str] = None
) -> Address:
    logger.info(f"Activating NIP-05 '{address_id}' for {auction_house_id}")

    address = await get_address(auction_house_id, address_id)
    assert address, f"Cannot find address '{address_id}' for {auction_house_id}."
    active_address = await get_active_address_by_local_part(
        auction_house_id, address.local_part
    )
    assert not active_address, f"Address '{address.local_part}' already active."

    address.extra.activated_by_owner = payment_hash is None
    address.extra.payment_hash = payment_hash
    address.active = True
    address.expires_at = datetime.now(timezone.utc) + timedelta(
        days=365 * address.extra.years
    )
    await update_address(address)
    logger.info(f"Activated NIP-05 '{address.local_part}' ({address_id}).")

    return address


async def get_valid_addresses_for_owner(
    owner_id: str, local_part: Optional[str] = None, active: Optional[bool] = None
) -> list[Address]:

    valid_addresses = []
    addresses = await get_addresses_for_owner(owner_id)
    for address in addresses:
        if active is not None and active != address.active:
            continue
        if local_part and address.local_part != local_part:
            continue
        auction_house = await get_auction_house_by_id(address.auction_house_id)
        if not auction_house:
            continue
        status = await get_identifier_status(
            auction_house,
            address.local_part,
            address.extra.years,
            address.extra.promo_code,
        )

        if status.available:
            # update to latest price
            address.extra.price_in_sats = status.price_in_sats
            address.extra.price = status.price
        elif not address.active:
            # do not return addresses which cannot be sold
            continue

        address.extra.currency = auction_house.currency

        valid_addresses.append(address)

    return valid_addresses


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


async def get_reimburse_wallet_id(address: Address) -> str:
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
