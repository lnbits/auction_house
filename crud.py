from typing import Optional

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    AuctionItem,
    AuctionItemFilters,
    AuctionRoom,
    AuctionRoomConfig,
    AuditEntry,
    AuditEntryFilters,
    Bid,
    BidFilters,
    CreateAuctionRoomData,
    EditAuctionRoomData,
    PublicAuctionItem,
    PublicAuctionRoom,
    PublicAuditEntry,
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
    user_id: Optional[str] = None,
    auction_item_ids: Optional[list[str]] = None,
    include_inactive: Optional[bool] = None,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[AuctionItem]:
    where = ["auction_room_id = :auction_room_id"]
    values = {"auction_room_id": auction_room_id}
    if user_id:
        where.append("user_id = :user_id")
        values["user_id"] = user_id
    if not include_inactive:
        where.append("active = true")

    if auction_item_ids:
        id_clause = []
        for i, item_id in enumerate(auction_item_ids):
            auction_item_id = f"auction_item_id__{i}"
            id_clause.append(f"id = :{auction_item_id}")
            values[auction_item_id] = item_id
        where.append(" OR ".join(id_clause))

    return await db.fetch_page(
        "SELECT * FROM auction_house.auction_items",
        where=where,
        values=values,
        filters=filters,
        model=AuctionItem,
    )


async def create_auction_item(data: AuctionItem):
    await db.insert("auction_house.auction_items", data)


async def update_auction_item(data: AuctionItem) -> AuctionItem:
    await db.update("auction_house.auction_items", data)
    return data


async def update_auction_item_top_price(
    auction_item_id: str, current_price: float
) -> None:
    await db.execute(
        """
        UPDATE auction_house.auction_items
        SET current_price = :current_price
        WHERE id = :auction_item_id
        """,
        {"auction_item_id": auction_item_id, "current_price": current_price},
    )


async def close_auction(auction_item_id: str) -> None:
    await db.execute(
        """
        UPDATE auction_house.auction_items
        SET active = false
        WHERE id = :auction_item_id
        """,
        {"auction_item_id": auction_item_id},
    )


async def get_auction_items(auction_room_id: str) -> list[PublicAuctionItem]:
    return await db.fetchall(
        """
            SELECT * FROM auction_house.auction_items
            WHERE auction_room_id = :auction_room_id
        """,
        {"auction_room_id": auction_room_id},
        PublicAuctionItem,
    )


async def get_active_auction_items() -> list[AuctionItem]:
    return await db.fetchall(
        """
            SELECT * FROM auction_house.auction_items
            WHERE active = true
        """,
        model=AuctionItem,
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


async def get_auction_item_by_id(item_id: str) -> Optional[AuctionItem]:
    return await db.fetchone(
        """
        SELECT * FROM auction_house.auction_items WHERE id = :id
        ORDER BY created_at DESC
        """,
        {"id": item_id},
        AuctionItem,
    )


async def get_auction_item_by_name(
    auction_room_id: str, name: str
) -> Optional[AuctionItem]:
    return await db.fetchone(
        """
        SELECT * FROM auction_house.auction_items
            WHERE auction_room_id = :auction_room_id
                AND name = :name
                AND active = true
        ORDER BY created_at DESC
        """,
        {"name": name, "auction_room_id": auction_room_id},
        AuctionItem,
    )


async def get_bid_by_payment_hash(payment_hash: str) -> Optional[Bid]:
    return await db.fetchone(
        """
        SELECT * FROM auction_house.bids WHERE payment_hash = :payment_hash
        ORDER BY created_at DESC
        """,
        {"payment_hash": payment_hash},
        Bid,
    )


async def create_bid(data: Bid) -> PublicBid:
    await db.insert("auction_house.bids", data)
    return PublicBid(**data.dict())


async def update_bid(data: Bid) -> Bid:
    await db.update("auction_house.bids", data)
    return data


async def update_top_bid(auction_item_id: str, bid_id: str) -> None:
    await db.execute(
        """
        UPDATE auction_house.bids
        SET higher_bid_made = true
        WHERE auction_item_id = :auction_item_id AND id != :bid_id
        """,
        {"auction_item_id": auction_item_id, "bid_id": bid_id},
    )


async def get_top_bid(auction_item_id: str) -> Optional[Bid]:
    return await db.fetchone(
        """
            SELECT * FROM auction_house.bids
            WHERE auction_item_id = :auction_item_id
                AND paid = true
                AND higher_bid_made = false
        """,
        {"auction_item_id": auction_item_id},
        Bid,
    )


async def get_bids(auction_item_id: str) -> list[Bid]:
    return await db.fetchall(
        """
            SELECT * FROM auction_house.bids
            WHERE auction_item_id = :auction_item_id AND paid = true
            ORDER BY amount DESC
        """,
        {"auction_item_id": auction_item_id},
        Bid,
    )


async def get_user_bidded_items_ids(user_id: str) -> list[str]:
    rows: list[dict] = await db.fetchall(
        """
            SELECT DISTINCT auction_item_id FROM auction_house.bids
            WHERE user_id = :user_id AND paid = true
        """,
        {"user_id": user_id},
    )
    return [row["auction_item_id"] for row in rows]


async def get_bids_paginated(
    auction_item_id: str,
    user_id: Optional[str] = None,
    include_unpaid: Optional[bool] = None,
    filters: Optional[Filters[BidFilters]] = None,
) -> Page[Bid]:
    where = ["auction_item_id = :auction_item_id"]
    values = {"auction_item_id": auction_item_id}
    if user_id:
        where.append(" user_id = :user_id")
        values["user_id"] = user_id
    if not include_unpaid:
        where.append("paid = true")

    return await db.fetch_page(
        "SELECT * FROM auction_house.bids",
        where=where,
        values=values,
        filters=filters,
        model=Bid,
    )


async def get_bids_for_user_paginated(
    user_id: str,
    filters: Optional[Filters[BidFilters]] = None,
) -> Page[PublicBid]:
    return await db.fetch_page(
        """
        SELECT * FROM auction_house.bids
        WHERE user_id = :user_id
        """,
        values={"user_id": user_id},
        filters=filters,
        model=PublicBid,
    )


async def create_audit_entry(entry_id: str, data: str) -> PublicAuditEntry:
    entry = PublicAuditEntry(entry_id=entry_id, data=data)
    await db.insert("auction_house.auction_audit", entry)
    return entry


async def get_audit_entry_paginated(
    entry_id: str,
    filters: Optional[Filters[AuditEntryFilters]] = None,
) -> Page[AuditEntry]:
    where = ["entry_id = :entry_id"]
    return await db.fetch_page(
        "SELECT * FROM auction_house.auction_audit",
        where=where,
        values={"entry_id": entry_id},
        filters=filters,
        model=AuditEntry,
    )
