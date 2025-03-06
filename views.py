from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from lnbits.core.models import User
from lnbits.decorators import check_user_exists, optional_user_id
from lnbits.helpers import template_renderer

from .crud import (
    get_auction_room,
    get_auction_room_public_data,
)

bids_generic_router: APIRouter = APIRouter()


def bids_renderer():
    return template_renderer(["bids/templates"])


@bids_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return bids_renderer().TemplateResponse(
        "bids/index.html", {"request": request, "user": user.json()}
    )


@bids_generic_router.get("/auction_room/{auction_room_id}", response_class=HTMLResponse)
async def auction_room_details(
    request: Request, auction_room_id: str, user: User = Depends(check_user_exists)
):
    auction_room = await get_auction_room(
        user_id=user.id, auction_room_id=auction_room_id
    )
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room does not exist.")
    return bids_renderer().TemplateResponse(
        "bids/auction_room.html",
        {
            "request": request,
            "auction_room": auction_room.json(),
            "user": user.json(),
        },
    )


@bids_generic_router.get("/auctions/{auction_room_id}", response_class=HTMLResponse)
async def auctions_list(
    request: Request,
    auction_room_id: str,
    user_id: Optional[str] = Depends(optional_user_id),
):
    auction_room = await get_auction_room_public_data(auction_room_id)
    if not auction_room:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Auction Room does not exist.")
    return bids_renderer().TemplateResponse(
        "bids/auctions.html",
        {
            "request": request,
            "is_user_authenticated": user_id is not None,
            "auction_room": auction_room.json(),
        },
    )
