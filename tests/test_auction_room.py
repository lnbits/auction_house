import pytest
from auction_house.crud import (  # type: ignore[import]
    create_auction_room,
    get_auction_room,
    update_auction_room,
)
from auction_house.models import (  # type: ignore[import]
    AuctionRoom,
    AuctionRoomConfig,
    EditAuctionRoomData,
)
from auction_house.services import get_user_auction_rooms  # type: ignore[import]
from lnbits.helpers import urlsafe_short_hash


@pytest.mark.asyncio
async def test_create_auction_rooms():
    user_id = "9e95a704fbc047d79edff94a1cdda70c"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="room one",
        fee_wallet_id="w123",
        currency="USD",
        type="auction",
        description="test 1 description",
        extra=AuctionRoomConfig(),
    )
    room_one = await create_auction_room(auction_room)
    assert room_one.id is not None
    assert room_one.user_id == user_id
    assert room_one.fee_wallet_id == "w123"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        fee_wallet_id="w123",
        currency="USD",
        type="fixed_price",
        name="room two",
        description="test 2 description",
        extra=AuctionRoomConfig(),
    )

    room_two = await create_auction_room(auction_room)
    assert room_two.id is not None
    assert room_two.user_id == user_id
    assert room_two.fee_wallet_id == "w123"
    assert room_two.type == "fixed_price"

    rooms = await get_user_auction_rooms(user_id=user_id)
    assert len(rooms) == 2


@pytest.mark.asyncio
async def test_update_auction_room():
    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id="123",
        fee_wallet_id="w123",
        currency="USD",
        name="test 1",
        type="auction",
        description="test 1 description",
        extra=AuctionRoomConfig(),
    )
    room = await create_auction_room(auction_room)
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
    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id="123",
        name="Old Name",
        fee_wallet_id="w123",
        type="auction",
        description="d1",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Old Name",
        fee_wallet_id="w123",
        type="auction",
        description="d1",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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
