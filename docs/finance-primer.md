# Finance Primer

Everything you need to read this project's database and judge whether the agent's answers are any good. Written for someone with no finance background.

- [1. Revenue, cost, profit](#1-revenue-cost-profit)
- [2. Why costs get split into layers](#2-why-costs-get-split-into-layers)
- [3. Profit and cash are not the same thing](#3-profit-and-cash-are-not-the-same-thing)
- [4. EBITDA](#4-ebitda)
- [5. Debt and leverage](#5-debt-and-leverage)
- [6. Vocabulary: share, mutual fund, index](#6-vocabulary-share-mutual-fund-index)
- [7. The three analysts](#7-the-three-analysts)
- [8. Same rows, three conclusions](#8-same-rows-three-conclusions)
- [Appendix A: the six logistics companies](#appendix-a-the-six-logistics-companies)
- [Appendix B: column reference](#appendix-b-column-reference)

---

## 1. Revenue, cost, profit

You own one delivery van. Over one month:

```
Customers pay you to deliver parcels ....... ₹100     REVENUE
You spend on fuel, driver, insurance ....... ₹70      COSTS
                                             ─────
What you actually keep ..................... ₹30      PROFIT
```

| Word | Means |
|---|---|
| **Revenue** | Total money customers gave you |
| **Costs** | Money spent running the business |
| **Profit** | Revenue − Costs |

**The trap:** revenue is not "how much money you made." A business with ₹100 revenue and ₹99 costs is doing far worse than one with ₹50 revenue and ₹20 costs. Nobody judges a company by revenue alone.

### Margin

To compare businesses of different sizes fairly, ask: *out of every ₹100 coming in, how much do I keep?*

```
Profit ÷ Revenue = 30 ÷ 100 = 30%
```

That percentage is a **margin**. UPS keeps about ₹4 of every ₹100. Microsoft keeps about ₹46.

---

## 2. Why costs get split into layers

One number for costs isn't enough, because different costs tell you different things.

```
Revenue ......................................... ₹100

  − Fuel + driver wages ......................... ₹55     scale with every delivery
                                                 ─────
  = GROSS PROFIT ................................ ₹45

  − Office rent, accountant, advertising ........ ₹15     paid even on a slow month
                                                 ─────
  = OPERATING PROFIT ............................ ₹30

  − Interest on your van loan ................... ₹8
  − Tax ......................................... ₹6
                                                 ─────
  = NET PROFIT .................................. ₹16
```

| Level | Question it answers |
|---|---|
| **Gross profit** | Is the actual service worth doing at all? |
| **Operating profit** | Is the whole business, run end to end, profitable? |
| **Net profit** | After the bank and government take their share, what's left? |

### Operating profit is the "business quality" number

Interest and tax aren't really about how good the business is:

- **Interest** depends on how much the owner chose to borrow
- **Tax** depends on which country the owner registered in

Two identical van businesses — one bought the van in cash, one took a loan — have the same business quality and very different interest. So to ask *"is this a good business?"*, stop at operating profit.

### Real-world wrinkle

**UPS doesn't report gross profit at all.** Transport companies report one lump of operating expenses and jump straight to operating profit. That's why `gross_profit` is only 33% populated in our database — not a bug, just how that industry files.

---

## 3. Profit and cash are not the same thing

> **Profit is an opinion. Cash is a fact.**

A company can be profitable on paper and still run out of money and die.

### Reason 1: you deliver now, you get paid later

Your van does ₹100 of deliveries. Corporate customers pay on 60-day terms, so only ₹80 has arrived.

Accounting records the sale when you **did the work**, not when money landed. Profit says ₹100, your bank says ₹80. Both correct, different questions.

### Reason 2: big purchases get spread out

You bought the van for **₹1,200 cash**. It lasts 5 years (60 months).

Accounting won't charge ₹1,200 to the month you bought it — that would make one month look catastrophic and 59 look great. Instead it charges **₹20 per month**. That ₹20 is **depreciation**.

| | Cash leaving your bank | Cost hitting your profit |
|---|---|---|
| **Month you buy the van** | ₹1,200 | ₹20 |
| **Every month after** | ₹0 | ₹20 |

Two consequences:

- **Depreciation is a cost with no cash attached**
- **Buying the van is cash with no cost attached** — this is called **capital expenditure**, or **capex**

### Where did the ₹1,200 go? It's a swap, not a cost

```
Before buying:                 After buying:
  Cash ........ ₹1,200           Cash ........ ₹0
  Van ......... ₹0               Van ......... ₹1,200
  ─────────────────              ─────────────────
  Total ....... ₹1,200           Total ....... ₹1,200   ← unchanged
```

**You are not poorer.** You hold your wealth in a different form. A cost makes you poorer; a swap doesn't. That's why it never appears on the profit statement.

The van sits on the **balance sheet** (the list of what you own and owe) and loses ₹20 of recorded value each month. That shrinking *is* the depreciation.

### The same ₹1,200, three views

| Statement | What it shows |
|---|---|
| **Profit statement** | ₹20 per month, for 60 months |
| **Balance sheet** | An asset starting at ₹1,200, shrinking ₹20 a month |
| **Cash statement** | ₹1,200 gone, all at once, in month 1 |

One event, three pictures. This is why three statements exist — no single one tells the whole truth.

### Free cash flow

```
cash_from_operations     cash that actually came in from running the business
− capital_expenditure    cash actually spent on vans, buildings, machines
  ────────────────────
= FREE CASH FLOW         cash genuinely left over
```

The number people trust most, because it's hardest to massage.

### Why cash can be HIGHER than profit

Net profit is calculated *after* subtracting depreciation — but depreciation never cost you cash. So you **add it back**:

```
PROFIT CALCULATION                    DID CASH MOVE?
Revenue                  ₹100         yes, ₹100 in
− Fuel + driver          ₹55          yes, ₹55 out
− Rent + office          ₹15          yes, ₹15 out
− Depreciation           ₹20          NO. No money moved.
                        ─────
= Operating profit       ₹10
− Interest               ₹8           yes, ₹8 out
                        ─────
= NET PROFIT             ₹2

Cash actually moved:  ₹100 in − ₹78 out  =  ₹22 in your pocket
```

Net profit ₹2, bank account ₹22. The difference is exactly the ₹20 depreciation.

```
Cash from operations = Net profit + Depreciation (± timing effects)
```

**Real UPS, quarter ending June 2026:**

```
Net profit ........................ ₹0.60 bn
+ Depreciation (added back) ....... ₹0.98 bn
                                   ──────────
                                    ₹1.58 bn
− Timing effects .................. ₹0.72 bn
                                   ──────────
= Cash from operations ............ ₹0.86 bn
− Capex (planes, trucks, hubs) .... ₹0.69 bn
                                   ──────────
= Free cash flow .................. ₹0.17 bn
```

₹22.83 bn of revenue, and only **₹0.17 bn** genuinely free. Not a failing company — that's what a business owning planes and depots looks like.

---

## 4. EBITDA

**EBITDA is operating profit with depreciation added back.**

```
Operating profit .... ₹10
+ Depreciation ...... ₹20
                     ─────
= EBITDA ............ ₹30
```

The name lists what's excluded: **E**arnings **B**efore **I**nterest, **T**axes, **D**epreciation and **A**mortization.

*Amortization* is depreciation's twin, for things you can't touch — software, patents, a purchased brand. Always reported together, hence our column `depreciation_amortization`.

### Why it exists

All three excluded items depend on the **owner**, not the business:

- **Interest** — how much did the owner choose to borrow?
- **Tax** — which country did they register in?
- **Depreciation** — what did they pay for the assets, and over how many years is it written down?

When you buy a company, **you change all three.** You refinance, you're a different tax entity, and accounting rules make you restate the assets, resetting depreciation entirely.

So EBITDA strips out exactly the three things about to change. It's the closest thing to *"what does this business produce, regardless of who owns it."* **That's why private equity runs on it.**

### Real numbers

| | Operating margin | EBITDA margin |
|---|---|---|
| Microsoft | 46.3% | 57.2% |
| Oracle | 34.8% | 51.1% |
| UPS | 4.1% | 8.4% |
| Snowflake | −17.0% | −15.3% |

Oracle jumps 16 points — enormous data centres being written down. Snowflake barely moves — it rents its infrastructure.

### The danger

UPS's depreciation (₹0.98 bn) is **larger** than its operating profit (₹0.93 bn). EBITDA makes UPS look roughly twice as profitable as operating profit does — but those planes genuinely wear out and genuinely must be replaced with real cash.

EBITDA is useful for comparing across owners, and misleading if you forget what it ignores. Use it alongside free cash flow, never alone.

### In our database

Nobody files EBITDA. We calculate it in a view:

```sql
operating_income + COALESCE(depreciation_amortization, 0) AS ebitda
```

---

## 5. Debt and leverage

### The balance sheet: two ways to fund anything

A van costs ₹1,200:

```
Option A — all your own money        Option B — mostly borrowed
   Your cash ...... ₹1,200              Your cash ...... ₹200      EQUITY
   Borrowed ....... ₹0                  Bank loan ...... ₹1,000    DEBT
```

```
WHAT YOU OWN           WHO PAID FOR IT
Van .... ₹1,200   =    Debt ...... ₹1,000
                       Equity .... ₹200
```

Assets always equal debt plus equity — every rupee of stuff was funded by a lender or by you.

### Why borrow: leverage

The van earns **₹300 profit a year**:

| | Your money in | Profit after interest | Your return |
|---|---|---|---|
| **A — all own money** | ₹1,200 | ₹300 | **25%** |
| **B — borrowed ₹1,000 at 8%** | ₹200 | ₹300 − ₹80 = ₹220 | **110%** |

Same van, same ₹300. Borrowing multiplies your return on the money you actually put in.

### And why it's dangerous

Bad year, van earns only ₹60:

| | Profit after interest | Outcome |
|---|---|---|
| **A** | ₹60 | Thin year, fine |
| **B** | ₹60 − ₹80 = **−₹20** | Can't pay the bank. They take the van. |

The interest bill is **fixed**. Leverage magnifies gains *and* losses, and losses can kill you outright.

### Net debt

```
Net debt = total debt − cash

UPS:  ₹24.48 bn − ₹4.65 bn = ₹19.83 bn
```

### Leverage ratio

> *"How many years of earnings would it take to clear this debt?"*

```
Leverage = Net debt ÷ EBITDA
```

```
under 3x ....... comfortable
3x to 5x ....... stretched, lenders get nervous
above 5x ....... distressed
```

### Why TTM — a trap worth understanding

Net debt is a **snapshot** (owed on one day). EBITDA is a **flow** (earned over a period). Which period?

Your home loan is ₹50 lakh, salary ₹1 lakh/month:

```
Against monthly salary:  50 ÷ 1   = 50x     terrifying, and meaningless
Against annual salary:   50 ÷ 12  = 4.2x    the number a bank actually uses
```

The convention is **twelve months** — **TTM**, trailing twelve months. Our views sum four quarters and refuse to compute the ratio if fewer than four exist.

*(This was a real bug in this project: using one quarter made UPS look like 10.38x. Against TTM it's 2.10x.)*

### The negative-EBITDA guard

```
EBITDA ...... −₹50
Net debt .... ₹350
−50 into 350  →  −7.0x
```

**−7.0x looks low, and low means safe.** The truth is the opposite — this business can service *no* debt at all. Our views return `NULL` and a verdict of `not_financeable`.

**A missing answer is safer than a confident wrong one.** That principle runs through the whole system.

---

## 6. Vocabulary: share, mutual fund, index

### Share

A company splits its ownership into pieces and sells them. Each piece is a **share**. Buy 1 of 100 shares, you own 1% of the company. Traded at a **stock market** (NSE/BSE in India, NYSE/NASDAQ in the US).

UPS is split into roughly 840 million shares.

### Mutual fund

You have ₹10,000 but don't know which companies to buy. A mutual fund pools money from thousands of people and a professional spreads it across ~60 companies. You own a slice of the pool.

**Why:** spreading risk. All ₹10,000 in one company that collapses = you lose everything. Spread across 60 = the other 59 carry you.

### Index

How do you know if your fund manager did well? *"I made you 10%"* means nothing without a yardstick.

**An index is a fixed list of companies, plus a number tracking how that list did on average.**

```
Nifty 50   =  India's 50 biggest companies
S&P 500    =  America's 500 biggest companies
```

```
The index went up ........ 12%
Your manager made you .... 10%
```

Your manager did **worse** than a list nobody had to think about — and you can buy that list directly, for almost no fee.

---

## 7. The three analysts

### House analogy

```
Person A   buys a small share of 60 houses. Wants steady rent for 20 years.
Person B   buys nothing. Publishes "prices here will rise next year."
Person C   buys ONE rundown house with a loan, renovates it, sells in 5 years.
```

---

### 7.1 Mutual Fund Analyst

**Job:** decide which ~60 companies the fund holds.

**The trap:** the index already contains almost every big company. Hold a bit of everything and you get *exactly* index performance — making you pointless. To be worth anything you must **differ** from the index, and there are only two moves:

```
Hold MORE of some companies  ← the ones you think are better
Hold LESS of others          ← the ones you think are worse
```

**Which forces one question:** *is this above or below the typical company in the sector?* Not "is it good" — there's no button for good, only more-or-less.

```
ODFL ..... 29.9%          Hold all six equally and you get
XPO ...... 11.5%          exactly the sector average.
JBHT ......  7.4%
─────────── 6.3% ← middle    To BEAT it: more of the top,
CHRW ......  5.2%            less of the bottom.
UPS .......  4.1%
GXO .......  2.2%
```

**The median IS their decision line.** That's why their view compares everything to it.

**Two more constraints:**

- **Long-only** — they can only buy. If they think a company is terrible, their only move is *not owning it*. (Profiting from a falling price is called short selling; funds handling retirement savings are generally forbidden from it.)
- **Growth durability** — they hold for years and manage too much money to dart in and out. A company growing 8%, 9%, 7%, 8% is worth more to them than one growing 50% then falling 30%.

**View:** `v_mf_benchmark` — `operating_margin_vs_sector`, `revenue_growth_vs_sector`, `quarters_of_growth_last_4`

---

### 7.2 Equity Analyst

**Job:** they own nothing. They cover ~15 companies deeply and publish **Buy / Hold / Sell**. The mutual fund analyst is one of their readers.

**The core idea — a share price already contains what everyone knows.**

Everyone knows ODFL is brilliant, so people already pay a high price for it. **The excellence is already in the price.** Buying a great company does not automatically make you money.

```
Share price today ........... ₹100
Everyone expects ............ ₹10 per share this year

Earns ₹10  →  as expected  →  stays ₹100  →  you made ₹0
Earns ₹13  →  BETTER       →  jumps ₹125  →  you made ₹25
Earns ₹7   →  WORSE        →  drops ₹75   →  you lost ₹25
```

> **Prices move on how a company does versus what people already expected.**

**Exam analogy:** a student who always scores 95 scores 95 again — nobody reacts. That student scoring 60, or a 40-student scoring 70 — everyone talks. **The news is never the score. It's the change.**

**So they hunt surprises before they arrive:**

```
A great company quietly getting WORSE     →  will miss  →  SELL
A mediocre company quietly getting BETTER →  will beat  →  BUY
```

This is the **opposite** of the fund analyst. They ask about **level**; this person asks about **direction**. A below-middle company can be a screaming BUY if it's climbing.

Margins move before headlines do — that's the edge.

**View:** `v_equity_margin_trend` — `operating_margin_yoy_delta`, `margin_direction`, `revenue_yoy_growth`

```
ticker   margin now   CHANGE vs last year   direction
ODFL       29.9%          +5.35 points      expanding
GXO         2.2%          +4.12 points      expanding
XPO        11.5%          +3.78 points      expanding
JBHT        7.4%          +1.31 points      expanding
CHRW        5.2%          +0.81 points      expanding
UPS         4.1%          −3.66 points      COMPRESSING
```

Read the last column, not the first. Five improving, UPS the only one going backwards **while every competitor improves** — that's not an industry problem, it's a UPS problem.

---

### 7.3 PE Analyst

**PE = private equity.** They buy **100% of a company** and remove it from the stock market — **taking it private**.

**Why:** so they can do painful things without punishment. A public company closing 30 depots sees its price crash and its CEO attacked. A private one does it quietly. **Owning all of it means you can actually change it.**

**They pay with mostly borrowed money**, and the loan becomes the *bought company's* debt, repaid from its own cash:

```
Buying a company for ......... ₹1,000 crore
Their own money .............. ₹300 crore
Borrowed from banks .......... ₹700 crore
```

Five years later, company cash has paid down ₹300 of the loan, and they sell for ₹1,500:

```
Sale price ................... ₹1,500 crore
Pay off remaining loan ....... −₹400 crore
                              ─────────────
They keep .................... ₹1,100 crore
Originally put in ............ ₹300 crore
```

```
WITH BORROWING:   ₹300 in,   ₹1,100 out  →  3.7x
ALL OWN MONEY:    ₹1,000 in, ₹1,500 out  →  1.5x
```

**They made money two ways:** the company became more valuable (they fixed it), *and* the debt shrank using the company's own cash. That second one is why cash generation is life-or-death — no cash, no debt paydown, banks take the company.

**Three checks, in order:**

```
1. Can it carry the debt?     Steady cash? Room to borrow more?
2. Is something BROKEN?       A fixable problem worth money?
3. Can I sell it in 5 years?  Will someone want it once fixed?
```

**The flip:** a struggling company is *avoid* to the fund analyst, *maybe* to the equity analyst, and **the entire point** to this one. A perfectly-run company is **useless** — nothing left to improve. **They are shopping for problems they know how to fix.**

**View:** `v_pe_lbo_screen` — `net_debt_to_ebitda`, `debt_capacity_at_5x`, `fcf_conversion`, `margin_gap_to_sector_best`, `ebitda_uplift_if_best_in_class`

---

## 8. Same rows, three conclusions

### UPS

| | Sees | Verdict |
|---|---|---|
| **Mutual Fund** | 4.1% vs 6.3% median → 2.2 points below; growth in 1 of 4 quarters | **Avoid** — a below-middle company drags the fund below the index |
| **Equity** | −3.66 points, the only company compressing while five peers expand | **Sell** — moving the wrong way, and the market will notice |
| **PE** | 2.10x leverage, ₹27.4 bn borrowing room, 27.5-point gap to ODFL, ₹23.82 bn uplift | **Best target in the sector** |

**Two said avoid. One said it's the most interesting company here.** Nobody erred; nobody used different data.

> For the MF and Equity analyst, **a bad margin is a reason to stay away.**
> For the PE analyst, **a bad margin is the entire investment thesis** — it's what they'd buy the company in order to fix.

ODFL proves a truck-and-depot business *can* earn 29.9%. UPS earns 4.1%. To a stock picker that's a quality gap — just buy the better company. To a buyout firm it's ₹23.82 bn sitting on the table.

*(Honest caveats a real PE analyst would add: UPS converts only 22% of EBITDA into free cash versus ODFL's 51%, which slows debt paydown. And UPS is worth over ₹8 lakh crore — the logic is sound, the cheque isn't writable.)*

### GXO — the mirror image

| | Sees | Verdict |
|---|---|---|
| **Mutual Fund** | 2.2%, worst in sector, 4.1 points below median | **Avoid** |
| **Equity** | +4.12 points, second-best improvement, revenue +15.6% | **Interesting** — improving fast, and expectations are low |
| **PE** | 3.11x leverage, only ₹1.5 bn room, FCF conversion 0.03 | **No** — can't finance it |

Here the PE analyst is the *most* negative. The turnaround the equity analyst likes is irrelevant when the company already carries too much debt and converts almost nothing into cash.

### Why this is the whole project

The assignment requires the persona to change **how the agent reasons**, not how it talks. It isn't "write in a PE voice" — a PE analyst **computes different things**.

`ebitda_uplift_if_best_in_class` is a question the MF view never asks. That's why the personas live in **SQL views** rather than prompt text: the difference is structural and a reviewer can read it, instead of the model being told to "sound like a PE analyst" and hoping.

---

## Appendix A: the six logistics companies

| Ticker | Name | What they do |
|---|---|---|
| **UPS** | United Parcel Service | Brown delivery vans. Like Blue Dart / Delhivery, but global. |
| **ODFL** | Old Dominion Freight Line | Trucking — pallets between businesses, not to your house. |
| **XPO** | XPO Inc. | Same as ODFL. Trucking between businesses. |
| **JBHT** | J.B. Hunt | Trucking, plus containers on trains for long stretches. |
| **CHRW** | C.H. Robinson | **Owns no trucks.** A middleman matching shippers with truckers. |
| **GXO** | GXO Logistics | **Runs warehouses for other companies.** Nike outsources to them. |

### Business model determines margin

```
ODFL ..... 29.9%    owns trucks and depots — controls everything, captures everything
XPO ...... 11.5%
JBHT ......  7.4%
CHRW ......  5.2%   middleman: customer pays ₹100, trucker gets ₹95, keeps ₹5
                    (not a bad business — owns nothing, needed little capital)
UPS .......  4.1%   owns ODFL-style assets, earns CHRW-style margins  ← the anomaly
GXO .......  2.2%   fixed-fee warehouse contracts, little room to earn more
```

**UPS owning as much as ODFL while earning a fraction of its margin is the single most important fact in this sector** — and the reason the three analysts disagree.

---

## Appendix B: column reference

### `financials` — as-filed facts only

| Column | Plain meaning |
|---|---|
| `revenue` | Money customers paid |
| `cost_of_revenue` | Direct cost of delivering the service |
| `gross_profit` | revenue − cost_of_revenue |
| `operating_expenses` | Cost of running the business |
| `operating_income` | Profit from the business itself, before interest and tax |
| `depreciation_amortization` | Assets wearing out on paper. **No cash moves.** |
| `interest_expense` | Cost of borrowed money |
| `net_income` | The bottom line |
| `eps_diluted` | Net income per share |
| `cash_from_operations` | Real cash the business generated |
| `capital_expenditure` | Cash spent on trucks, buildings, machines |
| `cash_and_equivalents` | Money in the bank (snapshot) |
| `total_debt` | Borrowed money owed (snapshot) |
| `total_equity` | What shareholders own (snapshot) |
| `total_assets` | Everything owned (snapshot) |

### Derived in views — never stored

| Metric | Formula | Meaning |
|---|---|---|
| `ebitda` | operating_income + D&A | Earnings before financing and accounting choices |
| `free_cash_flow` | cash_from_ops − capex | What's genuinely left over |
| `net_debt` | total_debt − cash | Real debt burden. **NULL if debt unknown** |
| `operating_margin` | operating_income ÷ revenue | Cents kept per rupee of sales |
| `ebitda_ttm` | Sum of last 4 quarters | Twelve-month earnings |
| `net_debt_to_ebitda` | net_debt ÷ ebitda_ttm | Years of earnings to clear the debt |
| `fcf_conversion` | free_cash_flow_ttm ÷ ebitda_ttm | How much EBITDA becomes real cash |
| `*_yoy_delta` | this year − last year | The **change**, in percentage points |

### Honesty guards built into the views

| Guard | Why |
|---|---|
| `NULLIF(x, 0)` on every divisor | Division by zero → NULL, not an error |
| `CASE WHEN ebitda > 0` | Negative EBITDA makes leverage ratios meaningless |
| `net_debt` NULL when debt unknown | Never turn "no data" into "net cash" |
| `ttm_quarter_count = 4` | Never compute a 12-month ratio from partial history |
| `leverage_verdict` includes `unknown_no_debt_data` | Say "I don't know" rather than guess |
