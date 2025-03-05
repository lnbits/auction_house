from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from lnbits.core.models import SimpleStatus, WalletTypeInfo
from lnbits.core.services import create_invoice
from lnbits.db import Filters, Page
from lnbits.decorators import (
    optional_user_id,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi
from lnbits.utils.cache import cache

from .crud import (
    create_auction_house_internal,
    delete_address,
    delete_address_by_id,
    delete_auction_house,
    get_address,
    get_auction_house,
    get_auction_house_by_id,
    update_address,
    update_auction_house,
)
from .helpers import (
    owner_id_from_user_id,
    validate_pub_key,
)
from .models import (
    Address,
    AddressFilters,
    AddressStatus,
    AuctionHouse,
    CreateAddressData,
    CreateAuctionHouseData,
    EditAuctionHouseData,
    LnAddressConfig,
    UpdateAddressData,
)
from .services import (
    activate_address,
    check_address_payment,
    create_address,
    get_identifier_status,
    get_reimburse_wallet_id,
    get_user_addresses,
    get_user_addresses_paginated,
    get_user_auction_houses,
    get_valid_addresses_for_owner,
)

bids_api_router: APIRouter = APIRouter()
address_filters = parse_filters(AddressFilters)


@bids_api_router.get("/api/v1/auction_houses")
async def api_auction_houses(
    all_wallets: bool = Query(None),
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> list[AuctionHouse]:
    wallet = key_info.wallet
    auction_houses = await get_user_auction_houses(wallet.user, wallet.id, all_wallets)
    return auction_houses


@bids_api_router.get("/api/v1/auction_house/{auction_house_id}")
async def api_get_auction_house(
    auction_house_id: str, key_info: WalletTypeInfo = Depends(require_invoice_key)
):
    auction_house = await get_auction_house(auction_house_id, key_info.wallet.id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")
    return auction_house


@bids_api_router.post("/api/v1/auction_house", status_code=HTTPStatus.CREATED)
async def api_create_auction_house(
    data: CreateAuctionHouseData, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    data.validate_data()
    return await create_auction_house_internal(wallet_id=key_info.wallet.id, data=data)


@bids_api_router.put("/api/v1/auction_house")
async def api_update_auction_house(
    data: EditAuctionHouseData, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    data.validate_data()
    return await update_auction_house(wallet_id=wallet.wallet.id, data=data)


@bids_api_router.delete(
    "/api/v1/auction_house/{auction_house_id}", status_code=HTTPStatus.CREATED
)
async def api_auction_house_delete(
    auction_house_id: str,
    key_info: WalletTypeInfo = Depends(require_admin_key),
):
    # make sure the address belongs to the user
    deleted = await delete_auction_house(auction_house_id, key_info.wallet.id)
    return SimpleStatus(success=deleted, message="Deleted")


@bids_api_router.get("/api/v1/auction_house/{auction_house_id}/search")
async def api_search_identifier(
    auction_house_id: str, q: Optional[str] = None, years: Optional[int] = None
) -> AddressStatus:

    if not q:
        return AddressStatus(identifier="")

    auction_house = await get_auction_house_by_id(auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")

    return await get_identifier_status(auction_house, q, years or 1)


@bids_api_router.get("/api/v1/auction_house/{auction_house_id}/payments/{payment_hash}")
async def api_check_address_payment(auction_house_id: str, payment_hash: str):
    # todo: can it be replaced with websocket?
    paid = await check_address_payment(auction_house_id, payment_hash)
    return {"paid": paid}


@bids_api_router.get("/api/v1/addresses")
async def api_get_addresses(
    all_wallets: bool = Query(None),
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> list[Address]:
    return await get_user_addresses(
        key_info.wallet.user, key_info.wallet.id, all_wallets
    )


@bids_api_router.get(
    "/api/v1/addresses/paginated",
    name="Addresses List",
    summary="get paginated list of addresses",
    response_description="list of addresses",
    openapi_extra=generate_filter_params_openapi(AddressFilters),
    response_model=Page[Address],
)
async def api_get_addresses_paginated(
    all_wallets: bool = Query(None),
    filters: Filters = Depends(address_filters),
    key_info: WalletTypeInfo = Depends(require_invoice_key),
) -> Page[Address]:
    page = await get_user_addresses_paginated(
        key_info.wallet.user, key_info.wallet.id, all_wallets, filters
    )
    return page


@bids_api_router.delete("/api/v1/auction_house/{auction_house_id}/address/{address_id}")
async def api_delete_address(
    auction_house_id: str,
    address_id: str,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
):

    # make sure the address belongs to the user
    auction_house = await get_auction_house(auction_house_id, key_info.wallet.id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")
    address = await get_address(auction_house_id, address_id)
    if not address:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Address not found.")
    if address.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch.")
    await delete_address_by_id(auction_house_id, address_id)
    cache.pop(f"{auction_house_id}/{address.local_part}")


@bids_api_router.put(
    "/api/v1/auction_house/{auction_house_id}/address/{address_id}/activate"
)
async def api_activate_address(
    auction_house_id: str,
    address_id: str,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Address:
    # make sure the address belongs to the user
    auction_house = await get_auction_house(auction_house_id, key_info.wallet.id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")
    active_address = await activate_address(auction_house_id, address_id)
    cache.pop(f"{auction_house_id}/{active_address.local_part}")
    return active_address


@bids_api_router.get(
    "/api/v1/auction_house/{auction_house_id}/address/{address_id}/reimburse",
    dependencies=[Depends(require_admin_key)],
    status_code=HTTPStatus.CREATED,
)
async def api_address_reimburse(
    auction_house_id: str,
    address_id: str,
):

    # make sure the address belongs to the user
    auction_house = await get_auction_house_by_id(auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")

    address = await get_address(auction_house.id, address_id)
    if not address:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Address not found.")
    if address.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch.")

    wallet_id = await get_reimburse_wallet_id(address)

    payment_hash, payment_request = await create_invoice(
        wallet_id=wallet_id,
        amount=address.reimburse_amount,
        memo="Reimbursement for NIP-05 for",
        extra={
            "tag": "bids",
            "auction_house_id": auction_house_id,
            "address_id": address.id,
            "local_part": address.local_part,
            "action": "reimburse",
        },
    )

    return {
        "payment_hash": payment_hash,
        "payment_request": payment_request,
        "address_id": address.id,
    }


@bids_api_router.put("/api/v1/auction_house/{auction_house_id}/address/{address_id}")
async def api_update_address(
    auction_house_id: str,
    address_id: str,
    data: UpdateAddressData,
    w: WalletTypeInfo = Depends(require_admin_key),
) -> Address:

    data.validate_relays_urls()

    # make sure the auction_house belongs to the user
    auction_house = await get_auction_house(auction_house_id, w.wallet.id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")

    address = await get_address(auction_house_id, address_id)
    if not address:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Address not found.")
    if address.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch")

    _pubkey = data.pubkey or address.pubkey
    if not _pubkey:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Pubkey is required.")

    pubkey = validate_pub_key(_pubkey)
    address.pubkey = pubkey

    if data.relays:
        address.extra.relays = data.relays

    await update_address(address)
    cache.pop(f"{auction_house_id}/{address.local_part}")
    return address


@bids_api_router.post(
    "/api/v1/auction_house/{auction_house_id}/address", status_code=HTTPStatus.CREATED
)
async def api_request_address(
    address_data: CreateAddressData,
    auction_house_id: str,
    key_info: WalletTypeInfo = Depends(require_admin_key),
):
    address_data.normalize()

    # make sure the auction_house belongs to the user
    auction_house = await get_auction_house(auction_house_id, key_info.wallet.id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")

    if address_data.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch")

    address = await create_address(
        auction_house, address_data, key_info.wallet.id, key_info.wallet.user
    )
    if not address.extra.price_in_sats:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Cannot compute price. for {address_data.local_part}",
        )
    return {
        "payment_hash": None,
        "payment_request": None,
        **address.dict(),
    }


@bids_api_router.get("/api/v1/user/addresses")
async def api_get_user_addresses(
    user_id: Optional[str] = Depends(optional_user_id),
    local_part: Optional[str] = None,
    active: Optional[bool] = None,
):
    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)

    owner_id = owner_id_from_user_id(user_id)
    if not owner_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)
    return await get_valid_addresses_for_owner(owner_id, local_part, active)


@bids_api_router.delete(
    "/api/v1/user/auction_house/{auction_house_id}/address/{address_id}"
)
async def api_delete_user_address(
    auction_house_id: str,
    address_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):

    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)

    owner_id = owner_id_from_user_id(user_id)  # todo: allow for admins
    return await delete_address(auction_house_id, address_id, owner_id)


@bids_api_router.put(
    "/api/v1/user/auction_house/{auction_house_id}/address/{address_id}"
)
async def api_update_user_address(
    auction_house_id: str,
    address_id: str,
    data: UpdateAddressData,
    user_id: Optional[str] = Depends(optional_user_id),
) -> Address:

    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)

    data.validate_data()

    address = await get_address(auction_house_id, address_id)
    if not address:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Address not found.")
    if address.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch")

    owner_id = owner_id_from_user_id(user_id)
    if address.owner_id != owner_id:
        raise HTTPException(
            HTTPStatus.UNAUTHORIZED, "Address does not belong to this user."
        )

    if data.relays:
        address.extra.relays = data.relays

    for k, v in data.dict().items():
        setattr(address, k, v)

    await update_address(address)
    cache.pop(f"{auction_house_id}/{address.local_part}")

    return address


@bids_api_router.post(
    "/api/v1/user/auction_house/{auction_house_id}/address",
    status_code=HTTPStatus.CREATED,
)
async def api_request_user_address(
    address_data: CreateAddressData,
    auction_house_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):

    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)

    address_data.normalize()

    # make sure the address belongs to the user
    auction_house = await get_auction_house_by_id(address_data.auction_house_id)
    assert auction_house, "AuctionHouse does not exist."

    assert (
        address_data.auction_house_id == auction_house_id
    ), "AuctionHouse ID missmatch"

    return None


@bids_api_router.post(
    "/api/v1/user/auction_house/{auction_house_id}/address/{address_id}/lnaddress"
)
@bids_api_router.put(
    "/api/v1/user/auction_house/{auction_house_id}/address/{address_id}/lnaddress"
)
async def api_lnurl_create_or_update(
    auction_house_id: str,
    address_id: str,
    data: LnAddressConfig,
    user_id: Optional[str] = Depends(optional_user_id),
):
    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED)

    # make sure the address belongs to the user
    auction_house = await get_auction_house_by_id(auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")

    address = await get_address(auction_house.id, address_id)
    if not address:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Address not found.")
    if address.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch")
    if not address.active:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Address not active.")
    owner_id = owner_id_from_user_id(user_id)
    if address.owner_id != owner_id:
        raise HTTPException(
            HTTPStatus.UNAUTHORIZED, "Address does not belong to this user."
        )

    data.pay_link_id = address.extra.ln_address.pay_link_id
    address.extra.ln_address = data

    return SimpleStatus(
        success=True,
        message="Lightning address.",
    )
