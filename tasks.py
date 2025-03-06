import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_auction_house")

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "auction_house":
        return
