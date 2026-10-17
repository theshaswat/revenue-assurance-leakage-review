"""Revenue assurance reconciliation on the Olist public e-commerce data.

Bridge (no overlap between steps):
  value at list price -> pricing variance -> billed value -> unbilled / short-paid
  -> paid -> voucher-funded value above policy cap -> customer cash
"""
from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

# Policy assumptions. Olist has no price list or discount policy, so these are ours.
# Every one is repeated in README, report and SOP pack.
PRICE_TOL = 0.10      # billed price within +/-10% of list price is acceptable
MIN_SALES = 5         # list price needs >= 5 sales of the product in the quarter
PAY_TOL = 1.00        # R$ tolerance between billed value and amount paid
VOUCHER_CAP = 0.10    # voucher-funded share of an order allowed without approval


def load():
    r = lambda f, **k: pd.read_csv(RAW / f, **k)
    o = r("olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"])
    i = r("olist_order_items_dataset.csv")
    p = r("olist_order_payments_dataset.csv")
    return o, i, p


def run(price_tol=PRICE_TOL, voucher_cap=VOUCHER_CAP):
    o, i, p = load()

    it = i.groupby("order_id").agg(item_value=("price", "sum"), freight=("freight_value", "sum"), n_items=("price", "size"))
    pay = p.groupby("order_id").agg(paid=("payment_value", "sum"), n_pay=("payment_value", "size"))
    pay["voucher"] = p[p.payment_type == "voucher"].groupby("order_id").payment_value.sum()
    ord_ = o.set_index("order_id")[["order_status", "order_purchase_timestamp", "order_delivered_customer_date"]].join(it).join(pay)
    ord_[["item_value", "freight", "n_items", "paid", "voucher"]] = ord_[["item_value", "freight", "n_items", "paid", "voucher"]].fillna(0)
    ord_["billed"] = ord_.item_value + ord_.freight
    ord_["delivered"] = (ord_.order_status == "delivered") & ord_.order_delivered_customer_date.notna()
    ord_ = ord_.rename(columns={"order_purchase_timestamp": "purchased", "order_delivered_customer_date": "delivered_on"})

    # --- list price per product-quarter (median unit price, >= MIN_SALES sales)
    x = i.merge(ord_[["delivered", "purchased"]], left_on="order_id", right_index=True)
    x = x[x.delivered].copy()
    x["qtr"] = x.purchased.dt.to_period("Q").astype(str)
    g = x.groupby(["product_id", "qtr"]).price
    x["list_price"] = g.transform("median")
    x["n_sales"] = g.transform("size")
    t = x[x.n_sales >= MIN_SALES].copy()
    t["dev"] = t.price / t.list_price - 1
    under = t[t.dev < -price_tol].assign(leak=lambda d: d.list_price - d.price)
    over = t[t.dev > price_tol].assign(exposure=lambda d: d.price - d.list_price)
    value_at_list = t.list_price.sum()
    value_billed_tested = t.price.sum()

    # --- unbilled / short-paid: delivered orders paid less than billed
    d = ord_[ord_.delivered & (ord_.billed > 0)]
    unbilled = d[d.paid < d.billed - PAY_TOL].assign(leak=lambda z: z.billed - z.paid)
    no_pay = d[d.paid == 0]
    deliv_no_date = ord_[(ord_.order_status == "delivered") & ord_.delivered_on.isna()]

    # --- voucher-funded value above cap
    v = d[d.voucher > 0].copy()
    v["voucher_pct"] = v.voucher / v.billed
    vo = v[v.voucher_pct > voucher_cap].assign(leak=lambda z: z.voucher - voucher_cap * z.billed)

    # --- billed but not delivered
    nd = ord_[~ord_.delivered & (ord_.paid > 0) & ~ord_.order_status.isin(["shipped", "invoiced", "processing", "approved", "created"])]

    recon = ord_.groupby("order_status").agg(orders=("billed", "size"), billed=("billed", "sum"), paid=("paid", "sum")).sort_values("orders", ascending=False)
    recon["diff"] = recon.paid - recon.billed

    res = dict(
        ord=ord_, items_tested=t, under=under, over=over, unbilled=unbilled, no_pay=no_pay,
        deliv_no_date=deliv_no_date, vouchers=vo, voucher_orders=v, not_delivered=nd, recon=recon,
        n_delivered=int(d.shape[0]), billed_delivered=float(d.billed.sum()), paid_delivered=float(d.paid.sum()),
        n_items_total=int(len(i)), n_items_tested=int(len(t)), n_items_delivered=int(len(x)),
        value_at_list=float(value_at_list), value_billed_tested=float(value_billed_tested),
        leak_pricing=float(under.leak.sum()), exp_overbilled=float(over.exposure.sum()),
        leak_unbilled=float(unbilled.leak.sum()), leak_voucher=float(vo.leak.sum()),
    )
    return res


if __name__ == "__main__":
    r = run()
    for k, v in r.items():
        if not isinstance(v, (pd.DataFrame, pd.Series)):
            print(k, round(v, 2) if isinstance(v, float) else v)
    for k in ["under", "over", "unbilled", "no_pay", "deliv_no_date", "vouchers", "not_delivered"]:
        print(k, len(r[k]))
    print(r["recon"].round(0))
    for pt in (0.05, 0.10, 0.20):
        print("price tol", pt, round(run(price_tol=pt)["leak_pricing"]))
    for vc in (0.05, 0.10, 0.20):
        print("voucher cap", vc, round(run(voucher_cap=vc)["leak_voucher"]))
