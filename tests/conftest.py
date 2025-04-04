import asyncio
import os

import auction_house.migrations as ext_migrations  # type: ignore[import]
import pytest_asyncio
from auction_house.crud import db  # type: ignore[import]
from lnbits.core import migrations as core_migrations  # type: ignore[import]
from lnbits.core.db import db as core_db
from lnbits.core.helpers import run_migration

print("### conftest.py")


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire session (instead of per function)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_ext():
    if os.path.isfile(core_db.path):
        os.remove(core_db.path)
    async with core_db.connect() as conn:
        await run_migration(conn, core_migrations, "core")

    if os.path.isfile(db.path):
        os.remove(db.path)
    async with db.connect() as conn:
        await run_migration(conn, ext_migrations, "auction_house")
