from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from .. import services


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_lnurl_preserves_amount_comment_and_invoice_check(monkeypatch):
    request = AsyncMock(
        side_effect=[
            {
                "callback": "https://pay.example/cb",
                "minSendable": 1000,
                "maxSendable": 50000,
            },
            {"pr": "invoice"},
        ]
    )
    monkeypatch.setattr(services, "request_lnurl_json", request)
    monkeypatch.setattr(
        services.bolt11, "decode", lambda _: SimpleNamespace(amount_msat=21000)
    )
    assert (
        await services._ln_address_payment_request(
            "item", "alice@pay.example", 21, "bid"
        )
        == "invoice"
    )
    assert request.await_args.kwargs["params"] == {"amount": 21000, "comment": "bid"}
    request.reset_mock(side_effect=True)
    request.side_effect = [
        {
            "callback": "https://pay.example/cb",
            "minSendable": 1000,
            "maxSendable": 50000,
        },
        {"pr": "wrong-amount-invoice"},
    ]
    monkeypatch.setattr(
        services.bolt11, "decode", lambda _: SimpleNamespace(amount_msat=22000)
    )
    with pytest.raises(ValueError, match="Amount mismatch"):
        await services._ln_address_payment_request(
            "item", "alice@pay.example", 21, "bid"
        )


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [1, 51])
async def test_lnurl_preserves_sendable_limits(monkeypatch, amount):
    request = AsyncMock(
        return_value={
            "callback": "https://pay.example/cb",
            "minSendable": 2000,
            "maxSendable": 50000,
        }
    )
    monkeypatch.setattr(services, "request_lnurl_json", request)
    monkeypatch.setattr(services, "db_log", AsyncMock())
    with pytest.raises(ValueError, match="Amount too"):
        await services._ln_address_payment_request("item", "alice@pay.example", amount)
    request.assert_awaited_once()
