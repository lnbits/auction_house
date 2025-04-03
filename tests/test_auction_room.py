import pytest
import json
from auction_house.crud import (
    create_auction_room,
    get_auction_room,
    update_auction_room,
)
from auction_house.models import CreateAuctionRoomData, EditAuctionRoomData
from auction_house.services import get_user_auction_rooms


@pytest.mark.asyncio
async def test_create_auction_rooms():
    user_id = "9e95a704fbc047d79edff94a1cdda70c"
    data = CreateAuctionRoomData(
        fee_wallet_id="w123",
        currency="USD",
        name="room one",
        type="auction",
        description="test 1 description",
    )
    room_one = await create_auction_room(user_id=user_id, data=data)
    assert room_one.id is not None
    assert room_one.user_id == user_id
    assert room_one.fee_wallet_id == "w123"

    data = CreateAuctionRoomData(
        fee_wallet_id="w123",
        currency="USD",
        type = "fixed_price",
        name = "room two",
        description = "test 2 description"
    )

    room_two = await create_auction_room(user_id=user_id, data=data)
    assert room_two.id is not None
    assert room_two.user_id == user_id
    assert room_two.fee_wallet_id == "w123"
    assert room_two.type == "fixed_price"

    rooms = await get_user_auction_rooms(user_id=user_id)
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


@pytest.mark.asyncio
async def test_update_auction_room_not_found():
    # Attempt to update a non-existent auction room
    edit_data = EditAuctionRoomData(
        id="nonexistent",
        name="New Name",
        type="auction",
        description="d1",
        extra={},
        currency="USD",
    )
    with pytest.raises(ValueError, match="Cannot update auction room."):
        await update_auction_room(user_id="user123", data=edit_data)


@pytest.mark.asyncio
async def test_update_auction_room_unauthorized():
    # Create an auction room with a different user
    create_data = CreateAuctionRoomData(
        name="Old Name",
        fee_wallet_id="w123",
        type="auction",
        description="d1",
        extra={},
        currency="USD",
    )
    auction_room = await create_auction_room(user_id="user456", data=create_data)

    # Attempt to update the auction room with an unauthorized user
    edit_data = EditAuctionRoomData(
        id=auction_room.id,
        name="New Name",
        type="auction",
        description="d1",
        extra={},
        currency="USD",
    )
    with pytest.raises(ValueError, match="Cannot update auction room."):
        await update_auction_room(user_id="user123", data=edit_data)


@pytest.mark.asyncio
async def test_update_auction_room_type_change():
    # Create an auction room
    user_id = "user123"
    create_data = CreateAuctionRoomData(
        name="Old Name",
        fee_wallet_id="w123",
        type="auction",
        description="d1",
        extra={},
        currency="USD",
    )
    auction_room = await create_auction_room(user_id=user_id, data=create_data)

    # Attempt to change the type of the auction room
    edit_data = EditAuctionRoomData(
        id=auction_room.id,
        name="New Name",
        type="fixed_price",
        description="d1",
        extra={},
        currency="USD",
    )
    with pytest.raises(ValueError, match="Cannot change auction room type."):
        await update_auction_room(user_id=user_id, data=edit_data)
