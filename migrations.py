from lnbits.db import Database


async def m001_initial_invoices(db: Database):
    empty_dict: dict[str, str] = {}
    await db.execute(
        f"""
       CREATE TABLE bids.auction_houses (
            id TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,

            currency TEXT NOT NULL,
            days INTEGER NOT NULL,
            house_percentage REAL NOT NULL,
            min_bid_up_percentage REAL NOT NULL,

            extra TEXT NOT NULL DEFAULT '{empty_dict}',
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
   """
    )

    await db.execute(
        f"""
       CREATE TABLE bids.addresses (
           id TEXT PRIMARY KEY,
           auction_house_id TEXT NOT NULL,

           local_part TEXT NOT NULL,
           pubkey TEXT NOT NULL,

           active BOOLEAN NOT NULL DEFAULT false,

           time TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
   """
    )


async def m002_add_owner_id_to_addresess(db: Database):
    """
    Adds owner_id column to  addresses.
    """
    await db.execute("ALTER TABLE bids.addresses ADD COLUMN owner_id TEXT")


async def m004_add_auction_house_rankings_table(db: Database):

    await db.execute(
        """
       CREATE TABLE bids.identifiers_rankings (
           name TEXT PRIMARY KEY,
           rank INTEGER NOT NULL

       );
   """
    )


async def m005_add_auction_house_rankings_table(db: Database):

    await db.execute(
        """
       CREATE TABLE bids.settings (
           owner_id TEXT PRIMARY KEY,
           settings text

       );
   """
    )


async def m007_add_cost_extra_column_to_addresses(db: Database):
    """
    Adds extra, expires_at and reimburse_amount columns to  addresses.
    """
    await db.execute("ALTER TABLE bids.addresses ADD COLUMN extra TEXT")
    await db.execute("ALTER TABLE bids.addresses ADD COLUMN expires_at TIMESTAMP")
    await db.execute(
        "ALTER TABLE bids.addresses ADD COLUMN "
        "reimburse_amount REAL NOT NULL DEFAULT 0"
    )
