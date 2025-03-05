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
    AuctionHouseCostConfig,
    BidsSettings,
    CreateAddressData,
    CreateAuctionHouseData,
    EditAuctionHouseData,
    IdentifierRanking,
    PublicAuctionHouse,
    UserSetting,
)

db = Database("ext_bids")


async def get_domain(domain_id: str, wallet_id: str) -> Optional[AuctionHouse]:
    return await db.fetchone(
        "SELECT * FROM bids.domains WHERE id = :id AND wallet = :wallet",
        {"id": domain_id, "wallet": wallet_id},
        AuctionHouse,
    )


async def get_domain_by_id(domain_id: str) -> Optional[AuctionHouse]:
    return await db.fetchone(
        "SELECT * FROM bids.domains WHERE id = :id",
        {"id": domain_id},
        AuctionHouse,
    )


async def get_domain_public_data(domain_id: str) -> Optional[PublicAuctionHouse]:
    return await db.fetchone(
        "SELECT id, currency, cost, auction_house FROM bids.domains WHERE id = :id",
        {"id": domain_id},
        PublicAuctionHouse,
    )


async def get_domain_by_name(auction_house: str) -> Optional[AuctionHouse]:
    return await db.fetchone(
        "SELECT * FROM bids.domains WHERE auction_house = :auction_house",
        {"auction_house": auction_house.lower()},
        AuctionHouse,
    )


async def get_domains(wallet_ids: Union[str, list[str]]) -> list[AuctionHouse]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"SELECT * FROM bids.domains WHERE wallet IN ({q})",
        model=AuctionHouse,
    )


async def get_address(domain_id: str, address_id: str) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses
        WHERE domain_id = :domain_id AND id = :address_id
        """,
        {"domain_id": domain_id, "address_id": address_id},
        Address,
    )


async def get_active_address_by_local_part(
    domain_id: str, local_part: str
) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses
        WHERE active = true AND domain_id = :domain_id AND local_part = :local_part
        """,
        {"domain_id": domain_id, "local_part": normalize_identifier(local_part)},
        Address,
    )


async def get_addresses(domain_id: str) -> list[Address]:
    return await db.fetchall(
        "SELECT * FROM bids.addresses WHERE domain_id = :domain_id",
        {"domain_id": domain_id},
        Address,
    )


async def get_address_for_owner(
    owner_id: str, domain_id: str, local_part: str
) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT * FROM bids.addresses WHERE owner_id = :owner_id
        AND domain_id = :domain_id AND local_part = :local_part
        """,
        {"owner_id": owner_id, "domain_id": domain_id, "local_part": local_part},
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
        JOIN bids.domains d ON d.id = a.domain_id
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
        JOIN bids.domains d ON d.id = a.domain_id
        WHERE d.wallet IN ({q})
        """,
        filters=filters,
        model=Address,
    )


async def update_address(address: Address) -> Address:
    await db.update("bids.addresses", address)
    return address


async def delete_domain(domain_id: str, wallet_id: str) -> bool:
    auction_house = await get_domain(domain_id, wallet_id)
    if not auction_house:
        return False
    await db.execute(
        """
        DELETE FROM bids.addresses WHERE domain_id = :domain_id
        """,
        {"domain_id": domain_id},
    )

    await db.execute(
        "DELETE FROM bids.domains WHERE id = :id",
        {"id": domain_id},
    )

    return True


async def delete_address(domain_id, address_id, owner_id):
    await db.execute(
        """
        DELETE FROM bids.addresses
        WHERE domain_id = :domain_id AND id = :id AND owner_id = :owner_id
        """,
        {"domain_id": domain_id, "id": address_id, "owner_id": owner_id},
    )


async def delete_address_by_id(domain_id, address_id):
    await db.execute(
        """
        DELETE FROM bids.addresses
        WHERE domain_id = :domain_id AND id = :id
        """,
        {"domain_id": domain_id, "id": address_id},
    )


async def create_address_internal(
    data: CreateAddressData,
    owner_id: Optional[str] = None,
    extra: Optional[AddressExtra] = None,
) -> Address:
    expires_at = datetime.now(timezone.utc) + timedelta(days=365 * data.years)
    address = Address(
        id=urlsafe_short_hash(),
        domain_id=data.domain_id,
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


async def update_domain(
    wallet_id: str, data: EditAuctionHouseData
) -> Optional[AuctionHouse]:
    auction_house = await get_domain(data.id, wallet_id)
    if not auction_house:
        return None
    auction_house.currency = data.currency
    auction_house.cost = data.cost
    auction_house.cost_extra = data.cost_extra or auction_house.cost_extra
    await db.update("bids.domains", auction_house)

    return auction_house


async def create_domain_internal(
    wallet_id: str, data: CreateAuctionHouseData
) -> AuctionHouse:
    auction_house = AuctionHouse(
        id=urlsafe_short_hash(),
        wallet=wallet_id,
        time=datetime.now(timezone.utc),
        cost_extra=data.cost_extra or AuctionHouseCostConfig(),
        currency=data.currency,
        cost=data.cost,
        auction_house=data.auction_house.lower(),
    )
    await db.insert("bids.domains", auction_house)
    return auction_house


# todo: rename to identifier
async def create_identifier_ranking(name: str, rank: int):
    await db.execute(
        """
        INSERT INTO bids.identifiers_rankings(name, rank)
        VALUES (:name, :rank) ON CONFLICT (name) DO NOTHING
        """,
        {"name": normalize_identifier(name), "rank": rank},
    )


async def update_identifier_ranking(name: str, rank: int):
    await db.execute(
        """
        UPDATE bids.identifiers_rankings
        SET rank = :rank WHERE name = :name
        """,
        {"name": normalize_identifier(name), "rank": rank},
    )


async def get_identifier_ranking(name: str) -> Optional[IdentifierRanking]:
    return await db.fetchone(
        "SELECT * FROM bids.identifiers_rankings WHERE name = :name",
        {"name": normalize_identifier(name)},
        IdentifierRanking,
    )


async def delete_inferior_ranking(name: str, rank: int):
    await db.execute(
        """
        DELETE from bids.identifiers_rankings
        WHERE name = :name and rank > :rank
        """,
        {"name": normalize_identifier(name), "rank": rank},
    )


async def create_settings(settings: UserSetting) -> UserSetting:
    user_settings = await get_settings(settings.owner_id)
    if not user_settings:
        await db.insert("bids.settings", settings)
    else:
        await db.update("bids.settings", settings, "WHERE owner_id = :owner_id")
    return settings


async def get_settings(owner_id: str) -> Optional[BidsSettings]:
    user_settings = await db.fetchone(
        "SELECT * FROM bids.settings WHERE owner_id = :owner_id",
        {"owner_id": owner_id},
        UserSetting,
    )
    if user_settings:
        return user_settings.settings
    return None
