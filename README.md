# Revenue Assurance and Leakage Review

A reconciliation of orders, delivery records and payments for 99,441 Olist marketplace orders (Brazil, 2016 to 2018), looking for revenue that was earned but not collected. It ends in a ranked leakage table, one SOP per leakage type and a control checklist.

## Result

Delivered orders: 96,470, billed R$ 15,418,395. Value at risk identified: **R$ 317,375 (2.06% of billed)**.

| Rank | Leakage type | Exceptions | Value at risk |
|---|---|---|---|
| 1 | Discount outside policy (voucher-funded above 10% of the order) | 3,600 | R$ 295,795 |
| 2 | Pricing mismatch (billed more than 10% below list price) | 1,308 | R$ 21,239 |
| 3 | Unbilled or short-paid orders | 18 | R$ 341 |

Billed value and cash collected on delivered orders agree to within R$ 2,688, so the problem is discounts and prices, not missing payments. Separately, 1,239 cancelled or unavailable orders carry R$ 271,114 of payments; the data has no refund records, so this is flagged, not counted.

## Files

| File | What it is |
|---|---|
| `outputs/Revenue_Assurance_Review.pdf` | Findings, reconciliation by order status, method and assumptions |
| `outputs/SOP_and_Control_Checklist.pdf` | One SOP per leakage type, then the control checklist ranked by value at risk |
| `outputs/Leakage_Workbook.xlsx` | Summary (live formulas over the exception sheets), assumptions, every exception row |
| `src/analysis.py` | The reconciliation and tests |
| `src/build_outputs.py` | Builds the three files above |

## Run it

Download the dataset from Kaggle (`olistbr/brazilian-ecommerce`) into `data/raw/`, then:

```
pip install -r requirements.txt
python src/build_outputs.py
```

## Assumptions

Olist has no price list, discount policy or invoice table. The settings below are mine and sit at the top of `src/analysis.py`; change them and the outputs rebuild.

- Billed value is item price plus freight.
- List price is the median unit price of a product in its purchase quarter, for products with at least 5 sales (42% of delivered lines can be tested).
- Price tolerance is plus or minus 10%. Moving it to 5% gives R$ 30,525 of pricing leakage; 20% gives R$ 6,929.
- Voucher cap is 10% of the order. At 5% the discount figure is R$ 319,071; at 20% it is R$ 251,527.

To confirm you hold the same files, run `shasum -a 256 -c data/SHA256SUMS`.

## Tests

```
pytest -q
```

`tests/test_analysis.py` builds a small set of orders with one planted case per leakage type and asserts the reconciliation finds exactly those amounts. It runs in CI on every push. It proves the logic; the full-data result is the one in the report.

Limits: list price is observed, not contractual. Credit notes and reason codes are not in the data and are not tested.

## Data

Olist Brazilian E-Commerce Public Dataset, Kaggle, CC BY-NC-SA 4.0. The data is not redistributed here. Code is MIT; the outputs in `outputs/` are derived from the Olist data and carry the same CC BY-NC-SA 4.0 terms.
