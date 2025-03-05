import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .crud import get_address, update_address
from .models import Address
from .services import activate_address


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_bids")

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if not payment.extra or payment.extra.get("tag") != "bids":
        return

    auction_house_id = payment.extra.get("auction_house_id")
    address_id = payment.extra.get("address_id")
    action = payment.extra.get("action")

    if not auction_house_id or not address_id or not action:
        logger.info(
            f"Cannot {action} for payment '{payment.payment_hash}'."
            f"Missing auction_house ID ({auction_house_id})"
            f" or address ID ({address_id})."
        )
        return

    try:
        address = await get_address(auction_house_id, address_id)
        if not address:
            logger.info(
                f"Cannot find address for payment '{payment.payment_hash}'."
                f"Missing auction_house ID ({auction_house_id})"
                f" or address ID ({address_id})."
            )
            return

        await _handle_action(action, payment, address)
    except Exception as exc:
        logger.warning(exc)
        logger.info(f"Issues on {action} address `{auction_house_id}/{address_id}`")


async def _handle_action(action: str, payment: Payment, address: Address):
    if action == "activate":
        await _activate_address(payment, address)
    if action == "reimburse":
        address.reimburse_amount = 0
        await update_address(address)


async def _activate_address(payment: Payment, address: Address):
    await activate_address(address.auction_house_id, address.id, payment.payment_hash)
