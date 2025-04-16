from datetime import datetime, timezone

import httpx
import pytest
from auction_house.crud import (  # type: ignore[import]
    create_auction_item,
    create_auction_room,
    get_auction_items,
)
from auction_house.models import (  # type: ignore[import]
    AuctionItem,
    AuctionItemExtra,
    AuctionItemFilters,
    AuctionRoom,
    AuctionRoomConfig,
    CreateAuctionItem,
    Webhook,
)
from auction_house.services import (  # type: ignore[import]
    add_auction_item,
    get_auction_room_items_paginated,
)
from lnbits.db import Filter, Filters
from lnbits.helpers import urlsafe_short_hash


@pytest.mark.asyncio
async def test_add_auction_item_success():
    # Create an auction room
    user_id = "user123"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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
    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Test Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room description",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

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


@pytest.mark.asyncio
async def test_get_auction_room_items_paginated_no_items():
    # Create an auction room
    user_id = "user123"
    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Empty Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room with no items",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

    # Fetch paginated items
    page = await get_auction_room_items_paginated(auction_room=auction_room)

    # Assertions
    assert page.total == 0
    assert len(page.data) == 0


@pytest.mark.asyncio
async def test_get_auction_room_items_paginated_one_item():
    # Create an auction room
    user_id = "user123"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Single Item Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room with one item",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

    # Add one auction item
    item_data = CreateAuctionItem(
        name="Single Item",
        description="A single test item",
        ask_price=100.0,
        transfer_code="code123",
        ln_address=None,
    )
    await create_auction_item(
        AuctionItem(
            id="item123",
            auction_room_id=auction_room.id,
            user_id=user_id,
            name=item_data.name,
            description=item_data.description,
            ask_price=item_data.ask_price,
            expires_at=datetime.now(timezone.utc)
            + auction_room.extra.duration.to_timedelta(),
            extra=AuctionItemExtra(transfer_code="t1", wallet_id="w123"),
        )
    )

    # Fetch paginated items
    page = await get_auction_room_items_paginated(auction_room=auction_room)

    # Assertions
    assert page.total == 1
    assert len(page.data) == 1
    assert page.data[0].name == "Single Item"


@pytest.mark.asyncio
async def test_get_auction_room_items_paginated_multiple_items():
    # Create an auction room
    user_id = "user123"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Multi Item Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room with multiple items",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

    # Add multiple auction items
    for i in range(3):
        item_data = CreateAuctionItem(
            name=f"Item {i+1}",
            description=f"Test item {i+1}",
            ask_price=100.0 + i * 10,
            transfer_code=f"code{i+1}",
            ln_address=None,
        )
        await create_auction_item(
            AuctionItem(
                id=urlsafe_short_hash(),
                auction_room_id=auction_room.id,
                user_id=user_id,
                name=item_data.name,
                description=item_data.description,
                ask_price=item_data.ask_price,
                expires_at=datetime.now(timezone.utc)
                + auction_room.extra.duration.to_timedelta(),
                extra=AuctionItemExtra(transfer_code="t1", wallet_id="w123"),
            )
        )

    # Fetch paginated items
    page = await get_auction_room_items_paginated(auction_room=auction_room)

    # Assertions
    assert page.total == 3
    assert len(page.data) == 3
    assert page.data[0].name == "Item 1"
    assert page.data[1].name == "Item 2"
    assert page.data[2].name == "Item 3"


@pytest.mark.asyncio
async def test_get_auction_room_items_paginated_with_filters():
    # Create an auction room
    user_id = "user123"

    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        name="Filtered Room",
        fee_wallet_id="w123",
        type="auction",
        description="Room with filtered items",
        currency="USD",
        extra=AuctionRoomConfig(),
    )
    auction_room = await create_auction_room(auction_room)

    # Add multiple auction items
    for i in range(5):
        item_data = CreateAuctionItem(
            name=f"Item {i+1}",
            description=f"Test item {i+1}",
            ask_price=100.0 + i * 10,
            transfer_code=f"code{i+1}",
            ln_address=None,
        )
        await create_auction_item(
            AuctionItem(
                id=urlsafe_short_hash(),
                auction_room_id=auction_room.id,
                user_id=user_id,
                name=item_data.name,
                description=item_data.description,
                ask_price=item_data.ask_price,
                expires_at=datetime.now(timezone.utc)
                + auction_room.extra.duration.to_timedelta(),
                extra=AuctionItemExtra(transfer_code="t1", wallet_id="w123"),
            )
        )

    # Fetch paginated items with filters
    page = await get_auction_room_items_paginated(
        auction_room=auction_room,
        filters=Filters(
            filters=[Filter.parse_query("name", ["Item 3"], AuctionItemFilters)]
        ),
    )

    # Assertions
    assert page.total == 1
    assert len(page.data) == 1
    assert page.data[0].name == "Item 3"
