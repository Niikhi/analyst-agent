from typing import Literal

Kind = Literal["duration", "instant"]

DURATION_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_expenses": ["OperatingExpenses", "CostsAndExpenses"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "Depreciation",
        "DepreciationNonproduction",
        "AmortizationOfIntangibleAssets",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestExpenseNonoperating",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "cash_from_operations": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capital_expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
    ],
}

INSTANT_CONCEPTS: dict[str, list[str]] = {
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "inventory": ["InventoryNet", "InventoryFinishedGoods"],
    "total_assets": ["Assets"],
    "total_equity": ["StockholdersEquity"],
    "long_term_debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebt",
    ],
    "long_term_debt_current": [
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    ],
    "short_term_borrowings": ["ShortTermBorrowings", "OtherShortTermBorrowings", "DebtCurrent"],
    "combined_debt": ["DebtLongtermAndShorttermCombinedAmount"],
}

UNSIGNED_CONCEPTS = {"capital_expenditure"}

CUMULATIVE_CONCEPTS = {"cash_from_operations", "capital_expenditure"}

FINANCIAL_COLUMNS = [
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_expenses",
    "operating_income",
    "depreciation_amortization",
    "interest_expense",
    "net_income",
    "eps_diluted",
    "shares_diluted",
    "cash_from_operations",
    "capital_expenditure",
    "cash_and_equivalents",
    "inventory",
    "total_assets",
    "total_debt",
    "total_equity",
]

QUARTER_DAYS = (80, 100)
ANNUAL_DAYS = (350, 380)
