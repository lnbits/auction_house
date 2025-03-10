import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .services import new_bid_made


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_auction_house")

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "auction_house":
        return
    logger.debug(
        f"Auction House payment received: '{payment.payment_hash}: {payment.memo}'"
    )
    try:
        await new_bid_made(payment)
    except Exception as e:
        logger.warning(f"Error processing payment: {e}")
