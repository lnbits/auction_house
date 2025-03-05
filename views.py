from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer

from .crud import (
    get_domain_by_id,
)

bids_generic_router: APIRouter = APIRouter()


def bids_renderer():
    return template_renderer(["bids/templates"])


@bids_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return bids_renderer().TemplateResponse(
        "bids/index.html", {"request": request, "user": user.json()}
    )


@bids_generic_router.get("/auction_house/{domain_id}", response_class=HTMLResponse)
async def domain_details(
    request: Request, domain_id: str, user: User = Depends(check_user_exists)
):
    auction_house = await get_domain_by_id(domain_id)
    if not auction_house:
        raise HTTPException(HTTPStatus.NOT_FOUND, "AuctionHouse does not exist.")
    return bids_renderer().TemplateResponse(
        "bids/auction_house.html",
        {
            "request": request,
            "auction_house": auction_house.json(),
            "user": user.json(),
        },
    )
