from datetime import datetime, timezone
from typing import Optional, Union

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    AuctionHouse,
    AuctionHouseConfig,
    AuctionItem,
    AuctionItemFilters,
    CreateAuctionHouseData,
    EditAuctionHouseData,
    PublicAuctionHouse,
    PublicAuctionItem,
)

db = Database("ext_bids")


async def get_auction_house(
    user_id: str, auction_house_id: str
) -> Optional[AuctionHouse]:
    return await db.fetchone(
        "SELECT * FROM bids.auction_houses WHERE id = :id AND user_id = :user_id",
        {"id": auction_house_id, "user_id": user_id},
        AuctionHouse,
    )


async def get_auction_house_by_id(auction_house_id: str) -> Optional[AuctionHouse]:
    return await db.fetchone(
        "SELECT * FROM bids.auction_houses WHERE id = :id",
        {"id": auction_house_id},
        AuctionHouse,
    )


async def get_auction_house_public_data(
    auction_house_id: str,
) -> Optional[PublicAuctionHouse]:
    return await db.fetchone(
        "SELECT * " "FROM bids.auction_houses WHERE id = :id",
        {"id": auction_house_id},
        PublicAuctionHouse,
    )


async def get_auction_houses(user_id: str) -> list[AuctionHouse]:
    return await db.fetchall(
        "SELECT * FROM bids.auction_houses WHERE user_id = :user_id",
        {"user_id": user_id},
        model=AuctionHouse,
    )


async def create_auction_item(data: AuctionItem) -> PublicAuctionItem:
    await db.insert("bids.auction_items", data)
    return PublicAuctionItem(**data.dict())


async def get_address(auction_house_id: str, address_id: str) -> Optional[AuctionItem]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses
        WHERE auction_house_id = :auction_house_id AND id = :address_id
        """,
        {"auction_house_id": auction_house_id, "address_id": address_id},
        AuctionItem,
    )


async def get_auction_items(auction_house_id: str) -> list[PublicAuctionItem]:
    return await db.fetchall(
        "SELECT * FROM bids.auction_items WHERE auction_house_id = :auction_house_id",
        {"auction_house_id": auction_house_id},
        PublicAuctionItem,
    )


async def get_auction_items_for_user(user_id: str) -> list[PublicAuctionItem]:
    return await db.fetchall(
        """
        SELECT * FROM bids.auction_items WHERE user_id = :user_id
        ORDER BY time DESC
        """,
        {"user_id": user_id},
        PublicAuctionItem,
    )


async def get_all_addresses(wallet_ids: Union[str, list[str]]) -> list[AuctionItem]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"""
        SELECT a.* FROM bids.addresses a
        JOIN bids.auction_houses d ON d.id = a.auction_house_id
        WHERE d.wallet IN ({q})
        """,
        model=AuctionItem,
    )


async def get_auction_items_paginated(
    auction_house_id: str,
    filters: Optional[Filters[AuctionItemFilters]] = None,
) -> Page[PublicAuctionItem]:
    return await db.fetch_page(
        """
        SELECT * FROM bids.auction_items
        WHERE auction_house_id = :auction_house_id
        """,
        values={"auction_house_id": auction_house_id},
        filters=filters,
        model=PublicAuctionItem,
    )


async def update_address(address: AuctionItem) -> AuctionItem:
    await db.update("bids.addresses", address)
    return address


async def delete_auction_house(user_id: str, auction_house_id: str) -> bool:
    auction_house = await get_auction_house(
        user_id=user_id, auction_house_id=auction_house_id
    )
    if not auction_house:
        return False
    await db.execute(
        """
        DELETE FROM bids.addresses WHERE auction_house_id = :auction_house_id
        """,
        {"auction_house_id": auction_house_id},
    )

    await db.execute(
        "DELETE FROM bids.auction_houses WHERE id = :id",
        {"id": auction_house_id},
    )

    return True


async def delete_address(auction_house_id, address_id, owner_id):
    await db.execute(
        """
        DELETE FROM bids.addresses
        WHERE auction_house_id = :auction_house_id AND id = :id AND owner_id = :owner_id
        """,
        {"auction_house_id": auction_house_id, "id": address_id, "owner_id": owner_id},
    )


async def delete_address_by_id(auction_house_id, address_id):
    await db.execute(
        """
        DELETE FROM bids.addresses
        WHERE auction_house_id = :auction_house_id AND id = :id
        """,
        {"auction_house_id": auction_house_id, "id": address_id},
    )


async def create_auction_house_internal(
    user_id: str, data: CreateAuctionHouseData
) -> AuctionHouse:
    auction_house = AuctionHouse(
        id=urlsafe_short_hash(),
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        extra=AuctionHouseConfig(),
        **data.dict(),
    )
    await db.insert("bids.auction_houses", auction_house)
    return auction_house


async def update_auction_house(
    user_id: str, data: EditAuctionHouseData
) -> Optional[AuctionHouse]:
    auction_house = await get_auction_house(user_id=user_id, auction_house_id=data.id)
    if not auction_house or auction_house.user_id != user_id:
        return None
    if auction_house.type != data.type:
        raise ValueError("Cannot change auction house type.")

    await db.update(
        "bids.auction_houses", AuctionHouse(**{**auction_house.dict(), **data.dict()})
    )

    return auction_house
