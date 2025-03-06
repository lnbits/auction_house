import pytest
from fastapi import APIRouter

from .. import auction_house_ext, auction_house_start, auction_house_stop


# just import router and add it to a test router
@pytest.mark.asyncio
async def test_router():
    router = APIRouter()
    router.include_router(auction_house_ext)


@pytest.mark.asyncio
async def test_start_and_stop():
    auction_house_start()
    auction_house_stop()
