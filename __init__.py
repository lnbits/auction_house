import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import run_by_the_minute_task, wait_for_paid_invoices
from .views import auction_house_generic_router
from .views_api import auction_house_api_router

auction_house_static_files = [
    {
        "path": "/auction_house/static",
        "name": "auction_house_static",
    }
]

auction_house_ext: APIRouter = APIRouter(
    prefix="/auction_house", tags=["auction_house"]
)
auction_house_ext.include_router(auction_house_generic_router)
auction_house_ext.include_router(auction_house_api_router)

scheduled_tasks: list[asyncio.Task] = []


def auction_house_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def auction_house_start():
    from lnbits.tasks import create_permanent_unique_task

    task1 = create_permanent_unique_task("ext_auction_house", wait_for_paid_invoices)
    task2 = create_permanent_unique_task("ext_auction_house", run_by_the_minute_task)
    scheduled_tasks.append(task1)
    scheduled_tasks.append(task2)


__all__ = [
    "auction_house_ext",
    "auction_house_static_files",
    "auction_house_start",
    "auction_house_stop",
    "db",
]
