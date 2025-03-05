from http import HTTPStatus
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import HTTPException
from lnbits.core.crud import get_wallets
from lnbits.core.models import SimpleStatus, User, WalletTypeInfo
from lnbits.core.services import create_invoice
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_admin,
    check_user_exists,
    optional_user_id,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi
from lnbits.utils.cache import cache
from loguru import logger

from .crud import (
    create_auction_house_internal,
    create_settings,
    delete_address,
    delete_address_by_id,
    delete_auction_house,
    get_active_address_by_local_part,
    get_address,
    get_auction_house,
    get_auction_house_by_id,
    get_identifier_ranking,
    get_settings,
    update_address,
    update_auction_house,
    update_identifier_ranking,
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
    BidsSettings,
    CreateAddressData,
    CreateAuctionHouseData,
    EditAuctionHouseData,
    IdentifierRanking,
    LnAddressConfig,
    UpdateAddressData,
    UserSetting,
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
    refresh_buckets,
    request_user_address,
    update_identifiers,
    update_ln_address,
)

bids_api_router: APIRouter = APIRouter()
address_filters = parse_filters(AddressFilters)
rotation_secret_prefix = "nostr_nip_5_rotation_secret_"


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


@bids_api_router.get("/api/v1/auction_house/{auction_house_id}/nostr.json")
async def api_get_nostr_json(
    response: Response, auction_house_id: str, name: str = Query(None)
):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,OPTIONS"

    if not name:
        return {"names": {}, "relays": {}}

    cached_bids = cache.get(f"{auction_house_id}/{name}")
    if cached_bids:
        return cached_bids

    address = await get_active_address_by_local_part(auction_house_id, name)

    if not address:
        return {"names": {}, "relays": {}}

    bids = {
        "names": {address.local_part: address.pubkey},
        "relays": {address.pubkey: address.extra.relays},
    }

    cache.set(f"{auction_house_id}/{name}", bids, 600)

    return bids


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
    return await update_ln_address(active_address)


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
        memo=f"Reimbursement for NIP-05 for {address.local_part}@{auction_house.auction_house}",
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

    wallet_id = (await get_wallets(user_id))[0].id

    return await request_user_address(auction_house, address_data, wallet_id, user_id)


@bids_api_router.post(
    "/api/v1/public/auction_house/{auction_house_id}/address",
    status_code=HTTPStatus.CREATED,
)
async def api_request_public_user_address(
    address_data: CreateAddressData,
    auction_house_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):

    address_data.normalize()
    # make sure the address belongs to the user
    auction_house = await get_auction_house_by_id(address_data.auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse not found.")
    if address_data.auction_house_id != auction_house_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "AuctionHouse ID missmatch")

    wallet_id = (await get_wallets(user_id))[0].id if user_id else None
    # used when the user is not authenticated
    temp_user_id = rotation_secret_prefix + uuid4().hex

    resp = await request_user_address(
        auction_house, address_data, wallet_id or "", user_id or temp_user_id
    )
    if not user_id:
        resp["rotation_secret"] = temp_user_id

    return resp


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
    await update_ln_address(address)

    return SimpleStatus(
        success=True,
        message=f"Lightning address '{address.local_part}@{auction_house.auction_house}' updated.",
    )


@bids_api_router.put(
    "/api/v1/auction_house/ranking/{bucket}",
)
async def api_refresh_identifier_ranking(
    bucket: int,
    user: User = Depends(check_admin),
):
    owner_id = owner_id_from_user_id("admin" if user.admin else user.id)
    bids_settings = await get_settings(owner_id)
    if not bids_settings:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Settings for user not found.")

    headers = {"Authorization": f"Bearer {bids_settings.cloudflare_access_token}"}
    ranking_url = "https://api.cloudflare.com/client/v4/radar/datasets?limit=12&datasetType=RANKING_BUCKET"
    dataset_url = "https://api.cloudflare.com/client/v4/radar/datasets"

    async with httpx.AsyncClient(headers=headers) as client:
        await refresh_buckets(client, ranking_url, dataset_url, bucket)


@bids_api_router.patch(
    "/api/v1/auction_house/ranking/{bucket}",
    dependencies=[Depends(check_admin)],
)
async def api_add_identifier_ranking(bucket: int, request: Request):
    identifiers = (await request.body()).decode("utf-8").splitlines()
    logger.info(f"Updating {len(identifiers)} rankings.")
    await update_identifiers(identifiers, bucket)
    logger.info(f"Updated {len(identifiers)} rankings.")
    return {"count": len(identifiers)}


@bids_api_router.get(
    "/api/v1/ranking/search",
    dependencies=[Depends(check_admin)],
)
async def api_auction_house_search_address(
    q: Optional[str] = None,
) -> Optional[IdentifierRanking]:
    if not q:
        return None
    return await get_identifier_ranking(q)


@bids_api_router.put(
    "/api/v1/ranking",
    dependencies=[Depends(check_admin)],
)
async def api_auction_house_update_ranking(
    identifier_ranking: IdentifierRanking,
) -> Optional[IdentifierRanking]:
    return await update_identifier_ranking(
        identifier_ranking.name, identifier_ranking.rank
    )


@bids_api_router.post("/api/v1/settings")
@bids_api_router.put("/api/v1/settings")
async def api_settings_create_or_update(
    settings: BidsSettings,
    user: User = Depends(check_user_exists),
):
    owner_id = owner_id_from_user_id("admin" if user.admin else user.id)
    user_settings = UserSetting(owner_id=owner_id, settings=settings)
    await create_settings(user_settings)


@bids_api_router.get("/api/v1/settings")
async def api_get_settings(
    user: User = Depends(check_user_exists),
) -> BidsSettings:
    owner_id = owner_id_from_user_id("admin" if user.admin else user.id)
    bids_settings = await get_settings(owner_id)

    return bids_settings or BidsSettings()
