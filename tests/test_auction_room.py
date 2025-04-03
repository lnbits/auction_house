import pytest
from auction_house.crud import (
    create_auction_room,
    get_auction_room,
    update_auction_room,
)
from auction_house.models import CreateAuctionRoomData, EditAuctionRoomData
from auction_house.services import get_user_auction_rooms


@pytest.mark.asyncio
async def test_create_auction_rooms():
    data = CreateAuctionRoomData(
        fee_wallet_id="w123",
        currency="USD",
        name="test 1",
        type="auction",
        description="test 1 description",
    )
    room_one = await create_auction_room(user_id="123", data=data)
    assert room_one.id is not None
    assert room_one.user_id == "123"
    assert room_one.fee_wallet_id == "w123"

    data.type = "fixed_price"
    data.name = "test 2"
    data.description = "test 2 description"
    room_two = await create_auction_room(user_id="123", data=data)
    assert room_two.id is not None
    assert room_two.user_id == "123"
    assert room_two.fee_wallet_id == "w123"
    assert room_two.type == "fixed_price"

    rooms = await get_user_auction_rooms(user_id="123")
    assert len(rooms) == 2


@pytest.mark.asyncio
async def test_update_auction_room():
    data = CreateAuctionRoomData(
        fee_wallet_id="w123",
        currency="USD",
        name="test 1",
        type="auction",
        description="test 1 description",
    )
    room = await create_auction_room(user_id="123", data=data)
    await update_auction_room(
        user_id="123",
        data=EditAuctionRoomData(
            id=room.id,
            fee_wallet_id="w123456789",
            currency="EUR",
            name="test 1 updated",
            description="test 1 description updated",
            extra=room.extra,
        ),
    )
    updated_room = await get_auction_room(user_id="123", auction_room_id=room.id)
    assert updated_room.name == "test 1 updated"
    assert updated_room.description == "test 1 description updated"
    assert updated_room.currency == "EUR"
    assert updated_room.fee_wallet_id == "w123456789"
