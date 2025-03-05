import pytest
from fastapi import APIRouter

from .. import bids_ext, bids_start, bids_stop


# just import router and add it to a test router
@pytest.mark.asyncio
async def test_router():
    router = APIRouter()
    router.include_router(bids_ext)


@pytest.mark.asyncio
async def test_start_and_stop():
    bids_start()
    bids_stop()
