from http import HTTPStatus
from typing import Optional, Union

from fastapi import APIRouter, Depends
from fastapi.exceptions import HTTPException
from lnbits.core.models import SimpleStatus, User
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_user_exists,
    optional_user_id,
    parse_filters,
)
from lnbits.helpers import generate_filter_params_openapi

from .crud import (
    create_auction_room,
    delete_auction_room,
    get_auction_item_by_id,
    get_auction_item_by_name,
    get_auction_room,
    get_bids_paginated,
    get_top_bid,
    update_auction_room,
)
from .helpers import (
    check_user_id,
)
from .models import (
    AuctionItem,
    AuctionItemFilters,
    AuctionRoom,
    Bid,
    BidFilters,
    BidRequest,
    BidResponse,
    CreateAuctionItem,
    CreateAuctionRoomData,
    EditAuctionRoomData,
    PublicAuctionItem,
    PublicAuctionRoom,
    PublicBid,
)
from .services import (
    add_auction_item,
    get_auction_item,
    get_auction_room_items_paginated,
    get_user_auction_rooms,
    place_bid,
)

auction_house_api_router: APIRouter = APIRouter()
auction_items_filters = parse_filters(AuctionItemFilters)
bid_filters = parse_filters(BidFilters)

############################# AUCTION ROOMS #############################


@auction_house_api_router.get("/api/v1/auction_room")
async def api_get_auction_rooms(
    user: User = Depends(check_user_exists),
) -> list[AuctionRoom]:
    return await get_user_auction_rooms(user.id)


@auction_house_api_router.get("/api/v1/auction_room/{auction_room_id}")
async def api_get_auction_room(
    auction_room_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
) -> Union[AuctionRoom, PublicAuctionRoom]:

    auction_room = await get_auction_room(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")

    if user_id == auction_room.user_id:
        return auction_room

    return PublicAuctionRoom(**auction_room.dict())


@auction_house_api_router.post("/api/v1/auction_room", status_code=HTTPStatus.CREATED)
async def api_create_auction_room(
    data: CreateAuctionRoomData, user: User = Depends(check_user_exists)
):
    return await create_auction_room(user_id=user.id, data=data)


@auction_house_api_router.put("/api/v1/auction_room")
async def api_update_auction_room(
    data: EditAuctionRoomData, user: User = Depends(check_user_exists)
) -> AuctionRoom:
    auction_room = await get_auction_room(data.id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")
    if auction_room.user_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not authorized to edit this room.")
    if auction_room.auction_type != data.auction_type:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Cannot change auction room")
    for k, v in data.dict().items():
        setattr(auction_room, k, v)
    return await update_auction_room(auction_room)


@auction_house_api_router.delete(
    "/api/v1/auction_room/{auction_room_id}", status_code=HTTPStatus.CREATED
)
async def api_auction_room_delete(
    auction_room_id: str, user: User = Depends(check_user_exists)
):
    auction_room = await get_auction_room(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")
    if auction_room.user_id != user.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not authorized to delete this room.")

    deleted = await delete_auction_room(auction_room_id=auction_room_id)
    return SimpleStatus(success=deleted, message="Deleted")


############################# AUCTION ITEMS #############################


@auction_house_api_router.post(
    "/api/v1/items/{auction_room_id}", status_code=HTTPStatus.CREATED
)
async def api_create_auction_item(
    auction_room_id: str,
    data: CreateAuctionItem,
    user_id: str = Depends(check_user_id),
) -> PublicAuctionItem:
    auction_room = await get_auction_room(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")
    if not auction_room.is_open_room and auction_room.user_id != user_id:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Not authorized to add items to this room."
        )

    auction_item = await get_auction_item_by_name(auction_room_id, data.name)
    if auction_item:
        raise HTTPException(
            HTTPStatus.CONFLICT, "Auction Item with this name already exists."
        )

    return await add_auction_item(auction_room, user_id, data)


@auction_house_api_router.get(
    "/api/v1/items/{auction_room_id}/paginated",
    name="Auction Items List",
    summary="get paginated list of auction items",
    response_description="list of auction items",
    openapi_extra=generate_filter_params_openapi(AuctionItemFilters),
    response_model=Page[PublicAuctionItem],
)
async def api_get_auction_items_paginated(
    auction_room_id: str,
    include_inactive: Optional[bool] = None,
    only_mine: Optional[bool] = None,
    user_id: Optional[str] = Depends(optional_user_id),
    filters: Filters = Depends(auction_items_filters),
) -> Page[PublicAuctionItem]:
    auction_room = await get_auction_room(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")

    for_user_id = user_id if only_mine else None
    page = await get_auction_room_items_paginated(
        auction_room=auction_room,
        include_inactive=include_inactive,
        user_id=for_user_id,
        filters=filters,
    )
    return Page(data=[item.to_public(user_id) for item in page.data], total=page.total)


@auction_house_api_router.get(
    "/api/v1/items/{auction_item_id}",
    name="Get Auction Item",
    summary="Get the auction item with this is. "
    "If the user is the owner, return the full item, otherwise return a public item",
    response_description="An auction item or 404 if not found",
    response_model=PublicAuctionItem,
)
async def api_get_auction_item(
    auction_item_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
) -> Union[AuctionItem, PublicAuctionItem]:

    auction_item = await get_auction_item(auction_item_id)
    if not auction_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Item not found.")

    if auction_item.user_id == user_id:
        return auction_item
    return PublicAuctionItem(**auction_item.dict())


# todo: cancel sell item at any time
# cancel auction item if no bids


############################# BIDS #############################


@auction_house_api_router.put(
    "/api/v1/bids/{auction_item_id}",
    status_code=HTTPStatus.CREATED,
    response_model=BidResponse,
)
async def api_place_bid(
    auction_item_id: str,
    data: BidRequest,
    user_id: str = Depends(check_user_id),
) -> Bid:
    auction_item = await get_auction_item(auction_item_id)
    if not auction_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Item not found.")
    auction_room = await get_auction_room(auction_item.auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")
    if auction_item.active is False:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Auction closed.")
    if auction_item.next_min_bid > data.amount:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            f"Bid amount too low. Next min bid: {auction_item.next_min_bid}",
        )
    top_bid = await get_top_bid(auction_item_id)
    if top_bid and top_bid.user_id == user_id:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "You already have the top bid for this item."
        )
    return await place_bid(
        user_id=user_id, auction_room=auction_room, auction_item=auction_item, data=data
    )


@auction_house_api_router.get(
    "/api/v1/bids/{auction_item_id}/paginated",
    name="Bids List",
    summary="get paginated list of bids for an auction item",
    response_description="list of bids",
    openapi_extra=generate_filter_params_openapi(BidFilters),
    response_model=Page[PublicAuctionItem],
)
async def api_get_user_bids_paginated(
    auction_item_id: str,
    only_mine: bool = False,
    include_unpaid: bool = False,
    user_id: Optional[str] = Depends(optional_user_id),
    filters: Filters = Depends(bid_filters),
) -> Page[PublicBid]:
    auction_item = await get_auction_item_by_id(auction_item_id)
    if not auction_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Item not found.")

    auction_room = await get_auction_room(auction_item.auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")

    for_user_id = user_id if only_mine else None
    include_unpaid = include_unpaid and (user_id == auction_room.user_id)
    page = await get_bids_paginated(
        auction_item_id=auction_item_id,
        user_id=for_user_id,
        include_unpaid=include_unpaid,
        filters=filters,
    )
    return Page(data=[item.to_public(user_id) for item in page.data], total=page.total)
