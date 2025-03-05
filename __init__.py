import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import bids_generic_router
from .views_api import bids_api_router

bids_static_files = [
    {
        "path": "/bids/static",
        "name": "bids_static",
    }
]

bids_ext: APIRouter = APIRouter(prefix="/bids", tags=["bids"])
bids_ext.include_router(bids_generic_router)
bids_ext.include_router(bids_api_router)

scheduled_tasks: list[asyncio.Task] = []


def bids_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def bids_start():
    from lnbits.tasks import create_permanent_unique_task

    task = create_permanent_unique_task("ext_bids", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "bids_ext",
    "bids_static_files",
    "bids_start",
    "bids_stop",
    "db",
]
