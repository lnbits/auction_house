from datetime import datetime, timezone
from typing import Optional

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    AuctionItem,
    AuctionItemFilters,
    AuctionRoom,
    AuctionRoomConfig,
    Bid,
    CreateAuctionRoomData,
    EditAuctionRoomData,
    PublicAuctionItem,
    PublicAuctionRoom,
    PublicBid,
)

db = Database("ext_auction_house")


async def get_auction_room(user_id: str, auction_room_id: str) -> Optional[AuctionRoom]:
    return await db.fetchone(
        """
            SELECT * FROM auction_house.auction_rooms
            WHERE id = :id AND user_id = :user_id
        """,
        {"id": auction_room_id, "user_id": user_id},
        AuctionRoom,
    )


async def get_auction_room_by_id(auction_room_id: str) -> Optional[AuctionRoom]:
    return await db.fetchone(
        "SELECT * FROM auction_house.auction_rooms WHERE id = :id",
        {"id": auction_room_id},
        AuctionRoom,
    )


async def get_auction_room_public_data(
    auction_room_id: str,
) -> Optional[PublicAuctionRoom]:
    return await db.fetchone(
        "SELECT * " "FROM auction_house.auction_rooms WHERE id = :id",
        {"id": auction_room_id},
        PublicAuctionRoom,
    )


async def get_auction_rooms(user_id: str) -> list[AuctionRoom]:
    return await db.fetchall(
        "SELECT * FROM auction_house.auction_rooms WHERE user_id = :user_id",
        {"user_id": user_id},
        model=AuctionRoom,
    )


async def delete_auction_room(user_id: str, auction_room_id: str) -> bool:
    auction_room = await get_auction_room(
        user_id=user_id, auction_room_id=auction_room_id
    )
    if not auction_room:
        return False
    await db.execute(
        """
        DELETE FROM auction_house.auction_items WHERE auction_room_id = :auction_room_id
        """,
        {"auction_room_id": auction_room_id},
    )

    await db.execute(
        "DELETE FROM auction_house.auction_rooms WHERE id = :id",
        {"id": auction_room_id},
    )

    return True


async def create_auction_room(user_id: str, data: CreateAuctionRoomData) -> AuctionRoom:
    auction_room = AuctionRoom(
        id=urlsafe_short_hash(),
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        extra=AuctionRoomConfig(),
        **data.dict(),
    )
    await db.insert("auction_house.auction_rooms", auction_room)
    return auction_room


async def update_auction_room(
    user_id: str, data: EditAuctionRoomData
) -> Optional[AuctionRoom]:
    auction_room = await get_auction_room(user_id=user_id, auction_room_id=data.id)
    if not auction_room or auction_room.user_id != user_id:
        return None
    if auction_room.type != data.type:
        raise ValueError("Cannot change auction room type.")

    await db.update(
        "auction_house.auction_rooms",
        AuctionRoom(**{**auction_room.dict(), **data.dict()}),
    )

    return auction_room


async def get_auction_items_paginated(
    auction_room_id: str,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[PublicAuctionItem]:
    return await db.fetch_page(
        """
        SELECT * FROM auction_house.auction_items
        WHERE auction_room_id = :auction_room_id
        """,
        values={"auction_room_id": auction_room_id},
        filters=filters,
        model=PublicAuctionItem,
    )


async def create_auction_item(data: AuctionItem) -> PublicAuctionItem:
    await db.insert("auction_house.auction_items", data)
    return PublicAuctionItem(**data.dict())


async def get_auction_items(auction_room_id: str) -> list[PublicAuctionItem]:
    return await db.fetchall(
        """
            SELECT * FROM auction_house.auction_items
            WHERE auction_room_id = :auction_room_id
        """,
        {"auction_room_id": auction_room_id},
        PublicAuctionItem,
    )


async def get_auction_items_for_user(user_id: str) -> list[PublicAuctionItem]:
    return await db.fetchall(
        """
        SELECT * FROM auction_house.auction_items WHERE user_id = :user_id
        ORDER BY created_at DESC
        """,
        {"user_id": user_id},
        PublicAuctionItem,
    )


async def get_auction_item_by_id(item_id: str) -> Optional[PublicAuctionItem]:
    return await db.fetchone(
        """
        SELECT * FROM auction_house.auction_items WHERE id = :id
        ORDER BY created_at DESC
        """,
        {"id": item_id},
        PublicAuctionItem,
    )


async def create_bid(data: Bid) -> PublicBid:
    await db.insert("auction_house.bids", data)
    return PublicBid(**data.dict())
