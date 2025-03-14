from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from lnbits.core.models import User
from lnbits.decorators import check_user_exists, optional_user_id
from lnbits.helpers import template_renderer

from .crud import (
    get_auction_room,
    get_auction_room_by_id,
)
from .models import PublicAuctionRoom
from .services import get_auction_item

auction_house_generic_router: APIRouter = APIRouter()


def auction_house_renderer():
    return template_renderer(["auction_house/templates"])


@auction_house_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return auction_house_renderer().TemplateResponse(
        "auction_house/index.html", {"request": request, "user": user.json()}
    )


@auction_house_generic_router.get(
    "/auction_room/{auction_room_id}", response_class=HTMLResponse
)
async def auction_room_details(
    request: Request, auction_room_id: str, user: User = Depends(check_user_exists)
):
    auction_room = await get_auction_room(
        user_id=user.id, auction_room_id=auction_room_id
    )
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room does not exist.")
    return auction_house_renderer().TemplateResponse(
        "auction_house/auction_room.html",
        {
            "request": request,
            "auction_room": auction_room.json(),
            "user": user.json(),
        },
    )


@auction_house_generic_router.get(
    "/auctions/{auction_room_id}", response_class=HTMLResponse
)
async def auctions_list(
    request: Request,
    auction_room_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):
    auction_room = await get_auction_room_by_id(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room does not exist.")
    public_auction_room = (PublicAuctionRoom(**auction_room.dict()).json(),)
    return auction_house_renderer().TemplateResponse(
        "auction_house/auctions.html",
        {
            "request": request,
            "is_user_authenticated": user_id is not None,
            "is_user_room_owner": user_id == auction_room.user_id,
            "auction_room": public_auction_room,
        },
    )


@auction_house_generic_router.get(
    "/bids/{auction_item_id}", response_class=HTMLResponse
)
async def bids_list(
    request: Request,
    auction_item_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):
    auction_item = await get_auction_item(auction_item_id)
    if not auction_item:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Item does not exist.")
    auction_room = await get_auction_room_by_id(auction_item.auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room not found.")

    return auction_house_renderer().TemplateResponse(
        "auction_house/bids.html",
        {
            "request": request,
            "is_user_authenticated": user_id is not None,
            "is_user_room_owner": user_id == auction_room.user_id,
            "auction_item": auction_item.json(),
        },
    )
