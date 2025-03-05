from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from lnbits.db import Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .helpers import normalize_identifier
from .models import (
    Address,
    AddressExtra,
    AddressFilters,
    AuctionHouse,
    AuctionHouseConfig,
    CreateAddressData,
    CreateAuctionHouseData,
    EditAuctionHouseData,
    PublicAuctionHouse,
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
        "SELECT * "
        "FROM bids.auction_houses WHERE id = :id",
        {"id": auction_house_id},
        PublicAuctionHouse,
    )


async def get_auction_houses(user_id: str) -> list[AuctionHouse]:
    return await db.fetchall(
        "SELECT * FROM bids.auction_houses WHERE user_id = :user_id",
        {"user_id": user_id},
        model=AuctionHouse,
    )


async def get_address(auction_house_id: str, address_id: str) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses
        WHERE auction_house_id = :auction_house_id AND id = :address_id
        """,
        {"auction_house_id": auction_house_id, "address_id": address_id},
        Address,
    )


async def get_active_address_by_local_part(
    auction_house_id: str, local_part: str
) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses
        WHERE active = true AND auction_house_id = :auction_house_id
              AND local_part = :local_part
        """,
        {
            "auction_house_id": auction_house_id,
            "local_part": normalize_identifier(local_part),
        },
        Address,
    )


async def get_addresses(auction_house_id: str) -> list[Address]:
    return await db.fetchall(
        "SELECT * FROM bids.addresses WHERE auction_house_id = :auction_house_id",
        {"auction_house_id": auction_house_id},
        Address,
    )


async def get_address_for_owner(
    owner_id: str, auction_house_id: str, local_part: str
) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses WHERE owner_id = :owner_id
        AND auction_house_id = :auction_house_id AND local_part = :local_part
        """,
        {
            "owner_id": owner_id,
            "auction_house_id": auction_house_id,
            "local_part": local_part,
        },
        Address,
    )


async def get_addresses_for_owner(owner_id: str) -> list[Address]:
    return await db.fetchall(
        """
        SELECT * FROM bids.addresses WHERE owner_id = :owner_id
        ORDER BY time DESC
        """,
        {"owner_id": owner_id},
        Address,
    )


async def get_all_addresses(wallet_ids: Union[str, list[str]]) -> list[Address]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"""
        SELECT a.* FROM bids.addresses a
        JOIN bids.auction_houses d ON d.id = a.auction_house_id
        WHERE d.wallet IN ({q})
        """,
        model=Address,
    )


async def get_all_addresses_paginated(
    wallet_ids: Union[str, list[str]],
    filters: Optional[Filters[AddressFilters]] = None,
) -> Page[Address]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetch_page(
        f"""
        SELECT a.* FROM bids.addresses a
        JOIN bids.auction_houses d ON d.id = a.auction_house_id
        WHERE d.wallet IN ({q})
        """,
        filters=filters,
        model=Address,
    )


async def update_address(address: Address) -> Address:
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


async def create_address_internal(
    data: CreateAddressData,
    owner_id: Optional[str] = None,
    extra: Optional[AddressExtra] = None,
) -> Address:
    expires_at = datetime.now(timezone.utc) + timedelta(days=365 * data.years)
    address = Address(
        id=urlsafe_short_hash(),
        auction_house_id=data.auction_house_id,
        owner_id=owner_id,
        local_part=normalize_identifier(data.local_part),
        pubkey=data.pubkey,
        active=False,
        extra=extra or AddressExtra(),
        expires_at=expires_at,
        time=datetime.now(timezone.utc),
    )
    await db.insert("bids.addresses", address)
    return address


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
