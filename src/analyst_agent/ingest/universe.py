from dataclasses import dataclass


@dataclass(frozen=True)
class SectorDefinition:
    slug: str
    display_name: str
    coverage_note: str
    tickers: tuple[str, ...]


SECTORS: dict[str, SectorDefinition] = {
    "tech": SectorDefinition(
        slug="tech",
        display_name="Technology",
        coverage_note=(
            "US-listed enterprise software and cloud infrastructure names only. "
            "Excludes semiconductors, consumer hardware, internet platforms, and "
            "every private or non-US-listed company. Not a market-cap-weighted "
            "index and not representative of the sector as a whole."
        ),
        tickers=("MSFT", "ORCL", "CRM", "NOW", "ADBE", "SNOW"),
    ),
    "retail": SectorDefinition(
        slug="retail",
        display_name="Retail",
        coverage_note=(
            "US-listed general merchandise, warehouse club, and off-price retailers "
            "only. Excludes grocery-only chains, e-commerce pure-plays, specialty "
            "apparel, and non-US-listed companies."
        ),
        tickers=("WMT", "COST", "TGT", "TJX", "ROST", "DG"),
    ),
    "logistics": SectorDefinition(
        slug="logistics",
        display_name="Logistics",
        coverage_note=(
            "US-listed parcel, less-than-truckload, freight brokerage, and contract "
            "logistics names only. Excludes ocean carriers, passenger and cargo "
            "airlines, railroads, and non-US-listed companies."
        ),
        tickers=("UPS", "ODFL", "CHRW", "JBHT", "XPO", "GXO"),
    ),
}
