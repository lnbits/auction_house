from lnbits.db import Database


async def m001_initial_invoices(db: Database):
    empty_dict: dict[str, str] = {}
    await db.execute(
        f"""
       CREATE TABLE bids.auction_houses (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
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
       CREATE TABLE bids.auction_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            auction_house_id TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT true,

            name TEXT NOT NULL,
            description TEXT NOT NULL,

            starting_price REAL NOT NULL,
            current_price REAL NOT NULL,

            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},

            extra TEXT NOT NULL DEFAULT '{empty_dict}'
        );
   """
    )
