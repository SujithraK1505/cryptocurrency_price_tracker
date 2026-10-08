# Cryptocurrency Price Tracker

Selenium-powered Python tracker for the top cryptocurrencies on CoinMarketCap.

## Features

- Live JavaScript page scraping with Chrome WebDriver
- Top 10 coin name, symbol, USD price, 24-hour change, and market cap
- Headless mode by default; use `--visible` to watch Chrome
- Timestamped historical CSV logging
- Filtering with `--min-price` and `--min-change`
- Pandas report formatting
- Offline `--demo` mode for testing without internet or ChromeDriver

## Setup on Windows

```powershell
cd "C:\Users\Super Computers\crypto_price_tracker"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Run

Live scrape:

```powershell
py tracker.py
```

Filter coins priced above 100 USD and gaining at least 2 percent:

```powershell
py tracker.py --min-price 100 --min-change 2
```

Run with a visible browser:

```powershell
py tracker.py --visible
```

Offline test with sample output:

```powershell
py tracker.py --demo
```

The historical file is written to `data/crypto_prices.csv`. Each run appends a UTC timestamp, so the CSV can be used for trend analysis or dashboards.

## Expected demo output

```text
Source: demo data | Collected: 5 | Runtime: 0.01s

CRYPTOCURRENCY PRICE TRACKER
 rank     name symbol    price_usd change_24h_percent market_cap_usd
    1  Bitcoin    BTC   $68,100.25              +2.45% $1,340,000,000,000
    2 Ethereum    ETH    $3,520.10              +1.83%   $423,000,000,000
    3   Tether   USDT        $1.00              +0.01%   $112,000,000,000
    4      BNB    BNB      $595.40              -0.72%    $88,000,000,000
    5   Solana    SOL      $172.30              +4.61%    $79,000,000,000
```

CoinMarketCap may change its HTML selectors or apply rate limits. The `--demo` option validates the complete CSV, filter, and report flow without making a network request.
