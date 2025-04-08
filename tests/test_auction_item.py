from datetime import timedelta

import httpx
import pytest
from auction_house.crud import (  # type: ignore[import]
    create_auction_room,
    get_auction_items,
)
from auction_house.models import (  # type: ignore[import]
    AuctionRoom,
    AuctionRoomConfig,
    CreateAuctionItem,
    CreateAuctionRoomData,
    Webhook,
)
from auction_house.services import add_auction_item  # type: ignore[import]


@pytest.mark.asyncio
async def test_add_auction_item_success():
    # Create an auction room
    user_id = "user123"
    room_data = CreateAuctionRoomData(
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
    )
    auction_room = await create_auction_room(user_id=user_id, data=room_data)

    # Add an auction item
    item_data = CreateAuctionItem(
        name="Test Item",
        description="Item description",
        ask_price=100.0,
        transfer_code="code123",
        ln_address=None,
    )
    auction_item = await add_auction_item(auction_room, user_id, item_data)

    # Assertions
    assert auction_item.id is not None
    assert auction_item.name == "Test Item"
    assert auction_item.ask_price == 100.0
    assert auction_item.auction_room_id == auction_room.id

    # Verify the item is in the database
    items = await get_auction_items(auction_room_id=auction_room.id)
    assert len(items) == 1
    assert items[0].name == "Test Item"


@pytest.mark.asyncio
async def test_add_auction_item_negative_price():
    # Create an auction room
    user_id = "user123"
    room_data = CreateAuctionRoomData(
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra={"duration": timedelta(hours=1)},
    )
    auction_room = await create_auction_room(user_id=user_id, data=room_data)

    # Attempt to add an item with a negative price
    item_data = CreateAuctionItem(
        name="Invalid Item",
        description="Invalid description",
        ask_price=-10.0,
        transfer_code="code123",
        ln_address=None,
    )
    with pytest.raises(ValueError, match="Ask price must be positive."):
        await add_auction_item(auction_room, user_id, item_data)


@pytest.mark.asyncio
async def test_add_auction_item_invalid_ln_address():
    # Create an auction room
    user_id = "user123"
    room_data = CreateAuctionRoomData(
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra={"duration": timedelta(hours=1)},
    )
    auction_room = await create_auction_room(user_id=user_id, data=room_data)

    # Attempt to add an item with an invalid Lightning Address
    item_data = CreateAuctionItem(
        name="Invalid Item",
        description="Invalid description",
        ask_price=100.0,
        transfer_code="code123",
        ln_address="invalid_ln_address",
    )
    with pytest.raises(ValueError, match="Invalid Lightning Address:"):
        await add_auction_item(auction_room, user_id, item_data)


@pytest.mark.asyncio
async def test_add_auction_item_missing_webhook():
    # Create an auction room without a lock webhook
    user_id = "user123"
    room_data = CreateAuctionRoomData(
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra={"duration": timedelta(hours=1), "lock_webhook": {"url": None}},
    )
    auction_room = await create_auction_room(user_id=user_id, data=room_data)

    # Add an auction item
    item_data = CreateAuctionItem(
        name="Test Item",
        description="Item description",
        ask_price=100.0,
        transfer_code="code123",
        ln_address=None,
    )
    auction_item = await add_auction_item(auction_room, user_id, item_data)

    # Assertions
    assert auction_item.id is not None
    assert auction_item.extra.wallet_id is not None
    assert auction_item.extra.lock_code is None


@pytest.mark.asyncio
async def test_add_auction_item_lock_webhook_failure():
    user_id = "user123"
    auction_room = AuctionRoom(
        id="1234",
        user_id=user_id,
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra=AuctionRoomConfig(
            lock_webhook=Webhook(url="http://invalid-webhook-url.com")
        ),
    )

    # Attempt to add an auction item
    item_data = CreateAuctionItem(
        name="Test Item",
        description="Item description",
        ask_price=100.0,
        transfer_code="code123",
        ln_address=None,
    )
    with pytest.raises(httpx.ConnectError):
        await add_auction_item(auction_room, user_id, item_data)
