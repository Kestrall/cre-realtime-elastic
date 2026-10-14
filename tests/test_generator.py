from datetime import datetime, timezone

from cre.generator import OPERATIONS, CreGenerator


def test_meme_graine_meme_flux():
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    a = [CreGenerator(accounts=50, seed=1).event(now) for _ in range(1)]
    b = [CreGenerator(accounts=50, seed=1).event(now) for _ in range(1)]
    assert a == b


def test_cre_coherent():
    gen = CreGenerator(accounts=100, seed=7)
    for _ in range(2000):
        e = gen.event()
        direction, low, high = OPERATIONS[e["operation_type"]]
        assert e["direction"] == direction
        assert low <= e["amount"] <= high
        assert e["iban"].startswith("FR76") and len(e["iban"]) == 27
        assert (e["merchant_category"] is not None) == e["operation_type"].startswith("CB_")


def test_solde_suit_les_operations_comptabilisees():
    gen = CreGenerator(accounts=1, seed=3)
    balance = gen.accounts[0].balance
    for _ in range(500):
        e = gen.event()
        if e["status"] == "COMPTABILISE":
            balance = round(balance + (e["amount"] if e["direction"] == "CREDIT" else -e["amount"]), 2)
        assert e["balance_after"] == balance
