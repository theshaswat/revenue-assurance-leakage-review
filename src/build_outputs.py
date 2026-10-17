"""Builds outputs/: Excel workbook, review report PDF, SOP + control checklist PDF."""
import sys
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether

sys.path.insert(0, str(Path(__file__).parent))
from chartstyle import apply, C, save
sys.path.insert(0, str(Path(__file__).parent))
import analysis as A

OUT = Path(__file__).resolve().parents[1] / "outputs"
R = A.run()
SENS_P = {t: A.run(price_tol=t)["leak_pricing"] for t in (0.05, 0.10, 0.20)}
SENS_V = {c: A.run(voucher_cap=c)["leak_voucher"] for c in (0.05, 0.10, 0.20)}

rs = lambda v: f"R$ {v:,.0f}"
pc = lambda r: "<0.01%" if 0 < r < 0.0001 else f"{r:.2%}"
BIL = R["billed_delivered"]
types = [  # (id, name, exceptions, value)
    ("Discount outside policy", len(R["vouchers"]), R["leak_voucher"]),
    ("Pricing mismatch", len(R["under"]), R["leak_pricing"]),
    ("Unbilled / short-paid orders", len(R["unbilled"]), R["leak_unbilled"]),
]
types.sort(key=lambda t: -t[2])
TOTAL = sum(t[2] for t in types)
ID = {"Discount outside policy": "D", "Pricing mismatch": "P", "Unbilled / short-paid orders": "U"}

# ---------------------------------------------------------------- chart
apply()
fig, ax = plt.subplots(figsize=(7.2, 2.4))
names = [t[0] for t in types][::-1]; vals = [t[2] for t in types][::-1]
ax.barh(names, vals, color=C["primary"])
for y, v in enumerate(vals):
    ax.text(v + TOTAL * 0.01, y, rs(v), va="center", fontsize=9)
ax.set_xlim(0, TOTAL * 1.18)
ax.set_xlabel("Value at risk (R$)")
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x/1000:,.0f}k"))
ax.set_title(f"Voucher discounts above policy are {types[0][2]/TOTAL:.0%} of identified leakage", loc="left", fontsize=11)
chart = OUT / "leakage_by_type.png"
save(fig, str(chart)); plt.close(fig)

# ---------------------------------------------------------------- excel
wb = Workbook()
HDR = PatternFill("solid", fgColor="1F3A5F"); WH = Font(bold=True, color="FFFFFF")


def sheet(name, df, money=()):
    ws = wb.create_sheet(name)
    ws.append(list(df.columns))
    for c in ws[1]:
        c.fill, c.font = HDR, WH
    for row in df.itertuples(index=False):
        ws.append([None if pd.isna(v) else (v.to_pydatetime() if hasattr(v, "to_pydatetime") else v) for v in row])
    for j, col in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(j)].width = max(14, min(36, len(str(col)) + 4))
        if col in money:
            for r in range(2, ws.max_row + 1):
                ws.cell(r, j).number_format = '#,##0.00'
    ws.freeze_panes = "A2"
    return ws


def tidy(d, cols):
    d = d.reset_index() if d.index.name == "order_id" else d
    return d[cols].round(2)

un = tidy(R["unbilled"].sort_values("leak", ascending=False), ["order_id", "billed", "paid", "leak"]).rename(columns={"leak": "short_paid"})
pu = tidy(R["under"].sort_values("leak", ascending=False), ["order_id", "product_id", "qtr", "price", "list_price", "dev", "leak"]).rename(columns={"leak": "under_billed", "dev": "variance_pct"})
po = tidy(R["over"].sort_values("exposure", ascending=False), ["order_id", "product_id", "qtr", "price", "list_price", "dev", "exposure"]).rename(columns={"exposure": "over_billed", "dev": "variance_pct"})
vo = tidy(R["vouchers"].sort_values("leak", ascending=False), ["order_id", "billed", "voucher", "voucher_pct", "leak"]).rename(columns={"leak": "above_cap"})
nd = R["not_delivered"].reset_index()[["order_id", "order_status", "billed", "paid"]].round(2).sort_values("paid", ascending=False)

wb.remove(wb.active)
S = wb.create_sheet("Summary")
sheet("Unbilled", un, ("billed", "paid", "short_paid"))
sheet("Pricing_Under", pu, ("price", "list_price", "under_billed"))
sheet("Pricing_Over", po, ("price", "list_price", "over_billed"))
sheet("Voucher", vo, ("billed", "voucher", "above_cap"))
sheet("Not_Delivered", nd, ("billed", "paid"))
rc = R["recon"].reset_index().round(2)
sheet("Recon_by_status", rc, ("billed", "paid", "diff"))
wa = wb.create_sheet("Assumptions")
for r in [("Assumption", "Value", "Why"),
          ("List price", "Median unit price of the product in the purchase quarter, >= 5 sales", "Olist publishes no price list; this is the closest observable one"),
          ("Price tolerance", f"+/-{A.PRICE_TOL:.0%}", "Below list by more than this = pricing mismatch; above = over-billing exposure"),
          ("Payment tolerance", f"R$ {A.PAY_TOL:.2f}", "Rounding on instalments"),
          ("Voucher cap", f"{A.VOUCHER_CAP:.0%} of billed value", "Voucher-funded value above this needs approval; leakage = excess over the cap"),
          ("Billed value", "Item price + freight", "Olist has no invoice table; order lines are the billing record"),
          ("Delivered", "Status = delivered and a customer delivery date exists", ""),
          ("Currency", "Brazilian real (R$)", "Dataset currency; not converted")]:
    wa.append(r)
for c in wa[1]:
    c.fill, c.font = HDR, WH
wa.column_dimensions["A"].width, wa.column_dimensions["B"].width, wa.column_dimensions["C"].width = 20, 60, 70

S.append(["Revenue assurance and leakage review: summary (formulas read the exception sheets)"]); S["A1"].font = Font(bold=True, size=13)
S.append([])
S.append(["Leakage type", "Exceptions", "Value at risk (R$)", "% of delivered billed value"]); 
for c in S[3]:
    c.fill, c.font = HDR, WH
src = {"Discount outside policy": ("Voucher", "E"), "Pricing mismatch": ("Pricing_Under", "G"), "Unbilled / short-paid orders": ("Unbilled", "D")}
for k, (n, e, v) in enumerate(types):
    sh, col = src[n]; r = 4 + k
    S.append([n, f"=COUNTA({sh}!A2:A{wb[sh].max_row})", f"=SUM({sh}!{col}2:{col}{wb[sh].max_row})", f"=C{r}/$B$9"])
S.append(["Total", "=SUM(B4:B6)", "=SUM(C4:C6)", "=C7/$B$9"])
S.append([])
S.append(["Delivered billed value (R$)", R["billed_delivered"]])
S.append(["Delivered amount paid (R$)", R["paid_delivered"]])
S.append(["Billed vs paid difference (R$)", "=B10-B9"])
S.append(["Over-billing exposure, not counted as leakage (R$)", "=SUM(Pricing_Over!G2:G%d)" % wb["Pricing_Over"].max_row])
S.append(["Billed, not delivered: paid on cancelled/unavailable orders (R$)", "=SUM(Not_Delivered!D2:D%d)" % wb["Not_Delivered"].max_row])
for r in range(4, 14):
    for c in (2, 3):
        S.cell(r, c).number_format = '#,##0'
    S.cell(r, 4).number_format = '0.00%'
S.column_dimensions["A"].width = 58
for col in "BCD": S.column_dimensions[col].width = 26
wb.move_sheet("Summary", offset=-wb.index(S))
wb.move_sheet("Assumptions", offset=-(wb.index(wb["Assumptions"]) - 1))
wb.properties.creator = "Shaswat Sharma"
wb.save(OUT / "Leakage_Workbook.xlsx")

# ---------------------------------------------------------------- pdf styles
NAVY = colors.HexColor("#1F3A5F"); GREY = colors.HexColor("#F2F4F7"); LINE = colors.HexColor("#C9D0DA")
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=NAVY, spaceBefore=9, spaceAfter=4, keepWithNext=1)
B = ParagraphStyle("b", fontName="Helvetica", fontSize=9.2, leading=12.6, spaceAfter=3)
SM = ParagraphStyle("sm", parent=B, fontSize=8, leading=10.4, textColor=colors.HexColor("#555555"))
TC = ParagraphStyle("tc", parent=B, fontSize=8.2, leading=10.4, spaceAfter=0)
TH = ParagraphStyle("th", parent=TC, fontName="Helvetica-Bold", textColor=colors.white)
P = lambda t, s=B: Paragraph(t, s)


def table(rows, widths, num_cols=(), head=True):
    data = [[Paragraph(str(c), TH if (head and i == 0) else TC) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY)] + [("BACKGROUND", (0, i), (-1, i), GREY) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return t


def doc(path, title):
    def foot(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#777777"))
        c.drawString(18 * mm, 10 * mm, "Shaswat Sharma  |  " + title)
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {d.page}"); c.restoreState()
    return SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=17 * mm,
                             title=title, author="Shaswat Sharma"), foot

# ---------------------------------------------------------------- report
d, foot = doc(OUT / "Revenue_Assurance_Review.pdf", "Revenue Assurance and Leakage Review")
f = []
f += [P("Revenue Assurance and Leakage Review", H1),
      P("Olist Brazilian e-commerce orders, 2016 to 2018  |  Source: Olist public dataset (Kaggle, CC BY-NC-SA 4.0)  |  Currency: Brazilian real (R$)", SM), Spacer(1, 4)]
f += [P("1. Scope and result", H2),
      P(f"Reconciled {R['n_delivered']:,} delivered orders ({rs(BIL)} billed) against order lines, delivery records and payments, and tested three leakage types. "
        f"Identified value at risk is <b>{rs(TOTAL)}</b>, {TOTAL/BIL:.1%} of delivered billed value. Billed value and cash collected agree to within {rs(abs(R['paid_delivered']-BIL))} "
        f"on delivered orders, so the leakage sits in discounts and prices, not in missing payments.")]
rows = [["Rank", "Leakage type", "Exceptions", "Value at risk", "Share of leakage", "% of billed"]]
for k, (n, e, v) in enumerate(types, 1):
    rows.append([k, n, f"{e:,}", rs(v), f"{v/TOTAL:.1%}", pc(v/BIL)])
rows.append(["", "<b>Total</b>", f"<b>{sum(t[1] for t in types):,}</b>", f"<b>{rs(TOTAL)}</b>", "100%", f"{TOTAL/BIL:.2%}"])
f += [table(rows, [12, 62, 24, 30, 28, 20]), Spacer(1, 6), Image(str(chart), width=165 * mm, height=55 * mm)]

f += [P("2. Findings", H2),
      P(f"<b>F1  Discounts outside policy ({rs(R['leak_voucher'])}).</b> {len(R['vouchers']):,} of {len(R['voucher_orders']):,} voucher orders funded more than {A.VOUCHER_CAP:.0%} of the order with a voucher. "
        f"The median voucher order is {R['voucher_orders'].voucher_pct.median():.0%} voucher-funded and {int((R['voucher_orders'].voucher_pct>=0.99).sum()):,} are fully voucher-funded, so the result moves little with the cap: {rs(SENS_V[0.05])} at 5%, {rs(SENS_V[0.20])} at 20%. Value at risk is the voucher amount above the cap."),
      P(f"<b>F2  Pricing mismatches ({rs(R['leak_pricing'])}).</b> {len(R['under']):,} item lines were billed more than {A.PRICE_TOL:.0%} below the list price. "
        f"A further {len(R['over']):,} lines were billed more than {A.PRICE_TOL:.0%} above list ({rs(R['exp_overbilled'])}); that is a customer-dispute exposure and is not counted as leakage."),
      P(f"<b>F3  Unbilled or short-paid orders ({rs(R['leak_unbilled'])}).</b> {len(R['unbilled'])} delivered orders were paid less than billed; one delivered order has no payment record. Immaterial in value, "
        f"but cheap to control with a daily match."),
      P(f"<b>Observation, not leakage.</b> {len(R['not_delivered']):,} cancelled or unavailable orders carry payments of {rs(R['not_delivered'].paid.sum())}, and most unavailable orders have no order lines. "
        f"The data holds no refund records, so whether this cash was returned cannot be confirmed. Also {len(R['deliv_no_date'])} orders marked delivered have no delivery date.")]

rr = [["Order status", "Orders", "Billed (R$)", "Paid (R$)", "Paid minus billed"]]
for s, r in R["recon"].iterrows():
    rr.append([s, f"{int(r.orders):,}", f"{r.billed:,.0f}", f"{r.paid:,.0f}", f"{r['diff']:,.0f}"])
rr.append(["<b>Total</b>", f"<b>{int(R['recon'].orders.sum()):,}</b>", f"<b>{R['recon'].billed.sum():,.0f}</b>", f"<b>{R['recon'].paid.sum():,.0f}</b>", f"<b>{R['recon']['diff'].sum():,.0f}</b>"])
f += [KeepTogether([P("3. Reconciliation by order status", H2), table(rr, [42, 26, 36, 36, 34]), P("Billed = item price plus freight. Totals tie to the source tables.", SM)])]

f += [P("4. Method and assumptions", H2),
      P("Olist has no price list, discount policy or invoice table, so the policy parameters below are set by the reviewer. Each can be changed in <font face='Courier'>src/analysis.py</font> and the figures rebuild."),
      table([["Item", "Setting"],
             ["Billed value", "Item price plus freight per order (the order lines are the billing record)"],
             ["List price", f"Median unit price of the product in the purchase quarter, for products with at least {A.MIN_SALES} sales ({R['n_items_tested']:,} of {R['n_items_delivered']:,} delivered lines, {R['n_items_tested']/R['n_items_delivered']:.0%}, are testable)"],
             ["Price tolerance", f"Plus or minus {A.PRICE_TOL:.0%} of list. Sensitivity: 5% gives {rs(SENS_P[0.05])}, 20% gives {rs(SENS_P[0.20])}"],
             ["Short-pay tolerance", f"R$ {A.PAY_TOL:.2f} per order (instalment rounding)"],
             ["Voucher cap", f"{A.VOUCHER_CAP:.0%} of billed value without approval; leakage is the excess"],
             ["No double count", "Steps run in sequence: price variance is measured on item price, short-pay on billed less paid, voucher excess on the voucher payment. They draw on different amounts."]],
            [35, 135]),
      P("Limits: the list price is observed, not contractual, and a marketplace seller can price legitimately below the quarter median. Credit notes and reason codes do not exist in the data and are not tested. "
        "Findings show where to look; they are not confirmed losses.", SM)]
d.build(f, onFirstPage=foot, onLaterPages=foot)

# ---------------------------------------------------------------- SOP pack
d, foot = doc(OUT / "SOP_and_Control_Checklist.pdf", "Revenue Assurance SOPs and Control Checklist")
SOPS = {
 "Discount outside policy": dict(code="SOP-D", title="Voucher and discount approval", owner="Commercial Manager (approver); Revenue Assurance Analyst (monitor)", freq="Per order (preventive); monthly review (detective)",
   purpose=f"Stop voucher-funded discounts above the {A.VOUCHER_CAP:.0%} cap from reaching billing without approval.",
   scope="All orders where a voucher, coupon or promotion reduces the amount the customer pays.",
   steps=[f"Set the cap in the promotion engine: {A.VOUCHER_CAP:.0%} of order value per order unless an approval code is attached.",
          "Campaign owner submits each campaign with budget, eligible products and maximum voucher share; Commercial Manager signs before launch.",
          "At checkout the engine rejects a voucher above the cap unless a valid approval code is present.",
          "Revenue Assurance runs the voucher-share report each month: every order above the cap with no approval code.",
          "Analyst traces each exception to the campaign, confirms or rejects it, and logs the root cause.",
          "Unapproved campaigns are suspended; the Finance Controller books the excess as promotional cost."],
   controls=[["D-1", "Engine blocks voucher above cap without approval code", "Preventive, automated", "Per order", "Engine rule config; blocked-order log"],
             ["D-2", "Campaign sign-off before launch", "Preventive, manual", "Per campaign", "Signed campaign form"],
             ["D-3", "Monthly voucher-share exception report", "Detective, manual", "Monthly", "Report, trace notes, sign-off"]],
   kpi="Orders above cap with no approval code: target zero. Voucher-funded value as a share of billed value: tracked monthly."),
 "Pricing mismatch": dict(code="SOP-P", title="Price list control and variance review", owner="Pricing Manager (list); Revenue Assurance Analyst (review)", freq="Per order (preventive); weekly review (detective)",
   purpose=f"Make sure the price billed matches the approved list price within a {A.PRICE_TOL:.0%} tolerance.",
   scope="All item lines on delivered orders, every product and seller.",
   steps=["Pricing Manager keeps one approved price list with effective dates; every change needs a second approver.",
          f"Order system compares the billed unit price with the list price at order creation; variance beyond {A.PRICE_TOL:.0%} is held for review.",
          "Revenue Assurance runs the weekly price variance report: lines below list and lines above list, by product and seller.",
          "Under-billed lines: confirm whether a price change was approved; if not, correct the list or the listing and record the loss.",
          "Over-billed lines: refund or correct before the customer disputes the charge.",
          "Repeat offenders (same product or seller on three consecutive reports) go to the Pricing Manager."],
   controls=[["P-1", "Approved price list with dated changes and second approver", "Preventive, manual", "Per change", "Change log with approver"],
             ["P-2", "Order-time check of billed price against list; hold above tolerance", "Preventive, automated", "Per order", "System rule; hold queue"],
             ["P-3", "Weekly price variance report", "Detective, manual", "Weekly", "Report, resolution notes"]],
   kpi="Lines outside tolerance as a share of lines tested; value under-billed and over-billed each week."),
 "Unbilled / short-paid orders": dict(code="SOP-U", title="Order-to-cash match for delivered orders", owner="Accounts Receivable Lead", freq="Daily",
   purpose="Make sure every delivered order is billed and paid in full, or the gap is explained.",
   scope="All orders with status delivered, matched order by order.",
   steps=["Each day, list orders that reached delivered in the last 24 hours.",
          f"Match billed value (items plus freight) to payments received; flag any gap above R$ {A.PAY_TOL:.2f}.",
          "Flag delivered orders with no payment record and delivered orders with no delivery date.",
          "Collections follows up each flagged order within two working days.",
          "Any write-off of a short payment needs Finance Controller approval and a reason code.",
          "Close the day only when every flagged order is resolved or has a named owner and date."],
   controls=[["U-1", "Daily delivered-order to payment match", "Detective, automated", "Daily", "Match report"],
             ["U-2", "Hold at carrier handover for orders with no payment", "Preventive, automated", "Per order", "Hold log"],
             ["U-3", "Write-off approval with reason code", "Preventive, manual", "Per write-off", "Approved write-off form"]],
   kpi="Delivered orders unpaid or short-paid at day 7; value outstanding."),
}
f = []
for rank, (n, e, v) in enumerate(types, 1):
    s = SOPS[n]
    blk = [P(f"{s['code']}  {s['title']}", H1),
           P(f"Leakage rank {rank} of 3  |  {e:,} exceptions  |  Value at risk {rs(v)} ({pc(v/BIL)} of delivered billed value)", SM), Spacer(1, 4),
           table([["Owner", s["owner"]], ["Frequency", s["freq"]], ["Source finding", f"Revenue Assurance Review, finding F{ {'D':1,'P':2,'U':3}[ID[n]] }"]], [30, 140], head=False),
           P("Purpose", H2), P(s["purpose"]), P("Scope", H2), P(s["scope"]), P("Procedure", H2)]
    blk += [P(f"{k}. {t}", B) for k, t in enumerate(s["steps"], 1)]
    blk += [P("Key controls", H2), table([["ID", "Control", "Type", "Frequency", "Evidence kept"]] + s["controls"], [11, 66, 31, 22, 40]),
            P("Monitoring and escalation", H2), P(s["kpi"] + " Exceptions open longer than five working days go to the Finance Controller."),
            Spacer(1, 4), P("Review: SOP reviewed annually or after any change in policy limits. Records kept for the audit retention period.", SM), PageBreak()]
    f += blk

f += [P("Control checklist, ranked by value at risk", H1), P("Use at each review cycle. Tick when the control ran and evidence is filed.", SM), Spacer(1, 4)]
rows = [["Rank", "ID", "Control", "Type", "Frequency", "Owner", "Done"]]
own = {"D": "Commercial Mgr", "P": "Pricing Mgr", "U": "AR Lead"}
for rank, (n, e, v) in enumerate(types, 1):
    for c in SOPS[n]["controls"]:
        rows.append([f"{rank}<br/>{rs(v)}" if c is SOPS[n]["controls"][0] else "", c[0], c[1], c[2], c[3], own[ID[n]], "[  ]"])
rows.append(["Obs.", "B-1", f"Weekly reconciliation of cash received on cancelled and unavailable orders to refunds issued ({rs(R['not_delivered'].paid.sum())} unconfirmed)", "Detective, manual", "Weekly", "Finance Controller", "[  ]"])
f += [table(rows, [20, 10, 56, 28, 22, 25, 13])]
d.build(f, onFirstPage=foot, onLaterPages=foot)
print("built", [p.name for p in OUT.iterdir()])
