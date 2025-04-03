import asyncio
import os

import pytest
import pytest_asyncio
from auction_house.crud import db
from auction_house.migrations import m001_auction_rooms, m002_bids

print("### conftest.py")


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire session (instead of per function)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_ext():
    print("### init_ext", db.path)
    if os.path.isfile(db.path):
        os.remove(db.path)
    await m001_auction_rooms(db)
    await m002_bids(db)


@pytest.fixture(scope="session", autouse=True)
def foo():
    print("### fooo")
