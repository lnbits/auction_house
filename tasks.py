import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .services import checked_expired_auctions, queue_bid_paid


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_auction_house")

    while True:
        payment = await invoice_queue.get()
        await _on_invoice_paid(payment)


async def run_by_the_minute_task():
    minute_counter = 0
    while True:
        try:
            await checked_expired_auctions()
        except Exception as ex:
            logger.error(ex)

        minute_counter += 1
        await asyncio.sleep(60)


async def _on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "auction_house":
        return
    if payment.extra.get("is_refund", False):
        logger.debug(
            f"Auction House refund received: '{payment.payment_hash}: {payment.memo}'"
        )
        return
    if payment.extra.get("is_fee", False):
        logger.debug(
            f"Auction House fee received: '{payment.payment_hash}: {payment.memo}'"
        )
        return
    if payment.extra.get("is_owner_payment", False):
        logger.debug(
            f"Auction House fee received: '{payment.payment_hash}: {payment.memo}'"
        )
        return
    logger.debug(
        f"Auction House payment received: '{payment.payment_hash}: {payment.memo}'"
    )

    try:
        await queue_bid_paid(payment)
    except Exception as e:
        logger.warning(f"Error processing payment: {e}")
