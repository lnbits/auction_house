from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from lnbits.core.models import SimpleStatus, User, WalletTypeInfo
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_user_exists,
    optional_user_id,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi

from .crud import (
    create_auction_house_internal,
    delete_address,
    delete_auction_house,
    get_auction_house,
    get_auction_house_by_id,
    get_auction_items_for_user,
    update_auction_house,
)
from .helpers import (
    check_user_id,
    owner_id_from_user_id,
)
from .models import (
    AuctionHouse,
    AuctionItemFilters,
    CreateAuctionHouseData,
    CreateAuctionItem,
    EditAuctionHouseData,
    PublicAuctionItem,
)
from .services import (
    add_auction_item,
    get_auction_house_items_paginated,
    get_user_auction_houses,
)

bids_api_router: APIRouter = APIRouter()
auction_items_filters = parse_filters(AuctionItemFilters)


@bids_api_router.get("/api/v1/auction_houses")
async def api_get_auction_houses(
    user: User = Depends(check_user_exists),
) -> list[AuctionHouse]:
    return await get_user_auction_houses(user.id)


@bids_api_router.get("/api/v1/auction_house/{auction_house_id}")
async def api_get_auction_house(
    auction_house_id: str, user: User = Depends(check_user_exists)
):
    auction_house = await get_auction_house(
        user_id=user.id, auction_house_id=auction_house_id
    )
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction House not found.")
    return auction_house


@bids_api_router.post("/api/v1/auction_house", status_code=HTTPStatus.CREATED)
async def api_create_auction_house(
    data: CreateAuctionHouseData, user: User = Depends(check_user_exists)
):
    data.validate_data()
    return await create_auction_house_internal(user_id=user.id, data=data)


@bids_api_router.put("/api/v1/auction_house")
async def api_update_auction_house(
    data: EditAuctionHouseData, user: User = Depends(check_user_exists)
):
    data.validate_data()
    return await update_auction_house(user_id=user.id, data=data)


@bids_api_router.delete(
    "/api/v1/auction_house/{auction_house_id}", status_code=HTTPStatus.CREATED
)
async def api_auction_house_delete(
    auction_house_id: str, user: User = Depends(check_user_exists)
):
    deleted = await delete_auction_house(
        user_id=user.id, auction_house_id=auction_house_id
    )
    return SimpleStatus(success=deleted, message="Deleted")


############################# AUCTION ITEMS #############################


@bids_api_router.post(
    "/api/v1/{auction_house_id}/items", status_code=HTTPStatus.CREATED
)
async def api_create_auction_item(
    auction_house_id: str,
    data: CreateAuctionItem,
    user_id: str = Depends(check_user_id),
) -> PublicAuctionItem:
    auction_house = await get_auction_house_by_id(auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction House not found.")

    return await add_auction_item(auction_house, user_id, data)


@bids_api_router.get(
    "/api/v1/{auction_house_id}/items/paginated",
    name="Auction Items List",
    summary="get paginated list of auction items",
    response_description="list of auction items",
    openapi_extra=generate_filter_params_openapi(AuctionItemFilters),
    response_model=Page[PublicAuctionItem],
)
async def api_get_auction_items_paginated(
    auction_house_id: str,
    filters: Filters = Depends(auction_items_filters),
) -> Page[PublicAuctionItem]:
    auction_house = await get_auction_house_by_id(auction_house_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction House not found.")

    page = await get_auction_house_items_paginated(auction_house, filters)
    return page


@bids_api_router.get("/api/v1/items")
async def api_get_user_auction_items(
    user_id: str = Depends(check_user_id),
) -> list[PublicAuctionItem]:
    return await get_auction_items_for_user(user_id=user_id)


@bids_api_router.delete("/api/v1/auction_house/{auction_house_id}/address/{address_id}")
async def api_delete_address(
    auction_house_id: str,
    address_id: str,
    key_info: WalletTypeInfo = Depends(require_invoice_key),
):

    # make sure the address belongs to the user
    pass


@bids_api_router.put(
    "/api/v1/auction_house/{auction_house_id}/address/{address_id}/activate"
)
async def api_activate_address(
    auction_house_id: str,
    address_id: str,
    key_info: WalletTypeInfo = Depends(require_admin_key),
):
    # make sure the address belongs to the user
    pass


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
