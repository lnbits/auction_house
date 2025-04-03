import pytest
from auction_house.crud import create_auction_room
from auction_house.models import CreateAuctionRoomData


@pytest.mark.asyncio
async def test_create_auction_room():
    data = CreateAuctionRoomData(
        fee_wallet_id="123",
        currency="USD",
        name="test 1",
        description="test 1 description",
    )
    await create_auction_room(user_id="123", data=data)
    await create_auction_room(user_id="234", data=data)
