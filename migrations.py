from lnbits.db import Database


async def m001_auction_rooms(db: Database):
    empty_dict: dict[str, str] = {}
    await db.execute(
        f"""
       CREATE TABLE auction_house.auction_rooms (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,

            currency TEXT NOT NULL,
            room_percentage REAL NOT NULL,
            min_bid_up_percentage REAL NOT NULL,
            is_open_room BOOLEAN NOT NULL DEFAULT false,

            extra TEXT NOT NULL DEFAULT '{empty_dict}',
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
       );
   """
    )

    await db.execute(
        f"""
       CREATE TABLE auction_house.auction_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            auction_room_id TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT true,
            transfer_code TEXT NOT NULL,

            name TEXT NOT NULL,
            description TEXT,

            ask_price REAL NOT NULL,
            current_price REAL NOT NULL,

            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},

            extra TEXT NOT NULL DEFAULT '{empty_dict}'
        );
   """
    )


async def m002_bids(db: Database):

    await db.execute(
        f"""
       CREATE TABLE auction_house.bids (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            auction_item_id TEXT NOT NULL,

            paid BOOLEAN NOT NULL DEFAULT true,
            higher_bid_made BOOLEAN NOT NULL DEFAULT true,

            payment_hash TEXT NOT NULL,
            memo TEXT NOT NULL,
            ln_address TEXT,

            amount REAL NOT NULL,
            amount_sat INT NOT NULL,
            currency TEXT NOT NULL,

            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}

        );
   """
    )
