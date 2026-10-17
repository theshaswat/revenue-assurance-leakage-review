"""The reconciliation must find exactly the leakage planted in a small hand-built set of orders."""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import analysis

orders, items, pays = [], [], []


def order(oid, price, paid_parts, freight=10.0, status="delivered"):
    orders.append(dict(order_id=oid, customer_id="c", order_status=status,
                       order_purchase_timestamp="2018-02-01 10:00:00",
                       order_delivered_customer_date="2018-02-05 10:00:00" if status == "delivered" else None))
    if price is not None:
        items.append(dict(order_id=oid, order_item_id=1, product_id="P1", seller_id="s", price=price, freight_value=freight))
    for k, (kind, value) in enumerate(paid_parts, 1):
        pays.append(dict(order_id=oid, payment_sequential=k, payment_type=kind, payment_installments=1, payment_value=value))


for k in range(1, 7):
    order(f"O{k}", 100.0, [("credit_card", 110.0)])        # clean, list price settles at 100
order("O7", 80.0, [("credit_card", 90.0)])                  # 20% under list: pricing leakage 20
order("O8", 130.0, [("credit_card", 140.0)])                # 30% over list: over-billing exposure 30
order("O9", 100.0, [("credit_card", 50.0)])                 # billed 110, paid 50: short-paid 60
order("O10", 100.0, [("voucher", 60.0), ("credit_card", 50.0)], freight=10.0)  # 60 voucher on 110 billed: excess 60 - 11 = 49
order("O11", None, [("credit_card", 40.0)], status="canceled")  # cash taken, nothing delivered


def test_planted_leakage_is_found(tmp_path, monkeypatch):
    pd.DataFrame(orders).to_csv(tmp_path / "olist_orders_dataset.csv", index=False)
    pd.DataFrame(items).to_csv(tmp_path / "olist_order_items_dataset.csv", index=False)
    pd.DataFrame(pays).to_csv(tmp_path / "olist_order_payments_dataset.csv", index=False)
    monkeypatch.setattr(analysis, "RAW", tmp_path)
    r = analysis.run()
    assert r["n_delivered"] == 10
    assert round(r["leak_pricing"], 2) == 20.0
    assert round(r["exp_overbilled"], 2) == 30.0
    assert round(r["leak_unbilled"], 2) == 60.0
    assert round(r["leak_voucher"], 2) == 49.0
    assert list(r["not_delivered"].index) == ["O11"]
