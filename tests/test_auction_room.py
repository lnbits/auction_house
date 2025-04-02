import pytest

from ..migrations import m001_auction_rooms, m002_bids

from ..crud import create_auction_room
from ..models import CreateAuctionRoomData
from .. import db


@pytest.mark.asyncio
async def test_create_auction_room():

    await m001_auction_rooms(db)
    await m002_bids(db)

    data = CreateAuctionRoomData(
        fee_wallet_id="123",
        currency="USD",
        name="test 1",
        description="test 1 description",
    )
    await create_auction_room(user_id="123", data=data)
    await create_auction_room(user_id="234", data=data)
