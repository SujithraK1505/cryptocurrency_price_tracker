"""Cryptocurrency Price Tracker using Selenium and CoinMarketCap."""

from __future__ import annotations

import argparse
import csv
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


CMC_URL = "https://coinmarketcap.com/"
OUTPUT_COLUMNS = [
    "timestamp_utc",
    "rank",
    "name",
    "symbol",
    "price_usd",
    "change_24h_percent",
    "market_cap_usd",
]


@dataclass
class Coin:
    timestamp_utc: str
    rank: int
    name: str
    symbol: str
    price_usd: float | None
    change_24h_percent: float | None
    market_cap_usd: float | None


def clean_number(value: str) -> float | None:
    """Convert currency/percentage text such as '$68,100.50' to a float."""
    if not value:
        return None
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value.replace("%", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def compact_number(value: str) -> float | None:
    """Parse values with K/M/B/T suffixes used by market-cap cells."""
    if not value:
        return None
    match = re.search(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*([KMBT]?)", value, re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(
        match.group(2).upper(), 1
    )
    return number * multiplier


def build_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )


def first_text(element, selectors: list[str]) -> str:
    for selector in selectors:
        found = element.find_elements(By.CSS_SELECTOR, selector)
        if found and found[0].text.strip():
            return found[0].text.strip()
    return ""


def scrape_coins(limit: int = 10, headless: bool = True) -> list[Coin]:
    """Load the JavaScript page and extract the first ``limit`` table rows."""
    driver = build_driver(headless)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    coins: list[Coin] = []
    try:
        driver.get(CMC_URL)
        rows = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        for row in rows[:limit]:
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            cell_text = [cell.text.strip() for cell in cells]
            if len(cell_text) < 4:
                continue

            rank_value = clean_number(cell_text[0]) or len(coins) + 1
            name = first_text(
                row,
                [
                    "p[class*='coin-item-name']",
                    "div[class*='coin-item-name']",
                    "a[href*='/currencies/']",
                ],
            )
            symbol = first_text(row, ["p[class*='coin-item-symbol']"])
            if not name:
                parts = cell_text[1].split("\n")
                name = parts[0]
                symbol = symbol or (parts[1] if len(parts) > 1 else "")

            price = first_text(row, ["a[href*='/currencies/'][class*='price']"])
            price = price or (cell_text[2] if len(cell_text) > 2 else "")
            change = first_text(
                row,
                ["span[class*='change-24h']", "td:nth-child(5) span"],
            )
            change = change or (cell_text[4] if len(cell_text) > 4 else "")
            market_cap = first_text(row, ["span[class*='market-cap']"])
            market_cap = market_cap or (cell_text[6] if len(cell_text) > 6 else "")

            coins.append(
                Coin(
                    timestamp_utc=timestamp,
                    rank=int(rank_value),
                    name=name,
                    symbol=symbol,
                    price_usd=clean_number(price),
                    change_24h_percent=clean_number(change),
                    market_cap_usd=compact_number(market_cap),
                )
            )
    finally:
        driver.quit()
    return coins


def demo_coins() -> list[Coin]:
    """Deterministic data for testing the CSV/filter/report pipeline offline."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [
        (1, "Bitcoin", "BTC", 68100.25, 2.45, 1.34e12),
        (2, "Ethereum", "ETH", 3520.10, 1.83, 4.23e11),
        (3, "Tether", "USDT", 1.00, 0.01, 1.12e11),
        (4, "BNB", "BNB", 595.40, -0.72, 8.80e10),
        (5, "Solana", "SOL", 172.30, 4.61, 7.90e10),
    ]
    return [Coin(timestamp, *row) for row in rows]


def save_history(coins: list[Coin], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    exists = output_file.exists()
    with output_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        if not exists or output_file.stat().st_size == 0:
            writer.writeheader()
        writer.writerows(asdict(coin) for coin in coins)


def filter_coins(
    coins: list[Coin], min_price: float | None, min_change: float | None
) -> list[Coin]:
    return [
        coin
        for coin in coins
        if (min_price is None or (coin.price_usd or 0) >= min_price)
        and (
            min_change is None
            or (coin.change_24h_percent or float("-inf")) >= min_change
        )
    ]


def print_report(coins: list[Coin], output_file: Path) -> None:
    if not coins:
        print("No coins matched the selected filters.")
        return
    frame = pd.DataFrame([asdict(coin) for coin in coins])
    frame["price_usd"] = frame["price_usd"].map(
        lambda value: f"${value:,.2f}" if pd.notna(value) else "N/A"
    )
    frame["change_24h_percent"] = frame["change_24h_percent"].map(
        lambda value: f"{value:+.2f}%" if pd.notna(value) else "N/A"
    )
    frame["market_cap_usd"] = frame["market_cap_usd"].map(
        lambda value: f"${value:,.0f}" if pd.notna(value) else "N/A"
    )
    print("\nCRYPTOCURRENCY PRICE TRACKER")
    print(frame[["rank", "name", "symbol", "price_usd", "change_24h_percent", "market_cap_usd"]].to_string(index=False))
    print(f"\nSaved {len(coins)} record(s) to: {output_file.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track top cryptocurrency prices.")
    parser.add_argument("--limit", type=int, default=10, help="Number of coins to collect")
    parser.add_argument("--output", type=Path, default=Path("data/crypto_prices.csv"))
    parser.add_argument("--min-price", type=float, help="Keep coins above this USD price")
    parser.add_argument("--min-change", type=float, help="Keep coins above this 24h change")
    parser.add_argument("--visible", action="store_true", help="Show the Chrome window")
    parser.add_argument("--demo", action="store_true", help="Run offline with sample data")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    if args.demo:
        coins = demo_coins()[: args.limit]
        source = "demo data"
    else:
        try:
            coins = scrape_coins(args.limit, headless=not args.visible)
            source = "CoinMarketCap"
        except WebDriverException as error:
            print(f"Scraping failed: {error.__class__.__name__}. Try --demo to test offline.")
            return

    filtered = filter_coins(coins, args.min_price, args.min_change)
    save_history(filtered, args.output)
    print(f"Source: {source} | Collected: {len(coins)} | Runtime: {time.perf_counter() - started:.2f}s")
    print_report(filtered, args.output)


if __name__ == "__main__":
    main()
