# PathOfTrading Repository Overview

## What This Repository Does

PathOfTrading is an optimization tool for Path of Exile currency trading that uses **Mixed Integer Linear Programming (MILP)** to find the most profitable sequence of currency exchanges.

### The Core Problem

In Path of Exile, you can trade currencies with NPCs, but:
- Each trade costs **gold**
- You can only make a **limited number of trades** per time window
- Currencies can only be traded in **whole units** (no fractional amounts)
- Exchange rates vary across different currency pairs

**Goal**: Convert your starting currency (e.g., 100 Chaos Orbs) into maximum target currency (e.g., Divine Orbs) by finding the optimal trading path through multiple currency types.

### The Solution

The optimizer uses:
1. **Graph representation**: Each currency pair becomes an edge in a directed graph
2. **MILP solver** (HiGHS via Pyomo): Handles the discrete constraints and gold costs
3. **Time-stepped optimization**: Plans trades across multiple time periods
4. **Real market data**: Now integrated with the official PoE Currency Exchange API

---

## Repository Structure

```
PathOfTrading/
├── src/pot/
│   ├── monad.py          # Functional programming utilities for Pyomo solver pipeline
│   ├── optimize.py       # Core MILP optimization model
│   └── api_client.py     # PoE Currency Exchange API integration (NEW)
├── tests/                # Unit tests
├── main.py              # Original example with hardcoded CSV data
├── inspect_api.py       # Tool to view raw API responses (NEW)
├── fetch_market_data.py # Full pipeline: API → optimization → results (NEW)
├── requirements.txt     # Python dependencies
├── .env                 # OAuth credentials (gitignored)
└── README.md           # Original project documentation
```

---

## What Was Built (API Integration)

### 1. OAuth Authentication (`src/pot/api_client.py`)

The `PoECurrencyAPI` class handles:
- OAuth 2.1 client_credentials grant flow
- Automatic token refresh
- Required User-Agent headers (critical for GGG API compliance)

```python
api = PoECurrencyAPI(
    client_id="ribeyemaker",
    client_secret="your_secret",
    realm="poe2",        # 'pc', 'xbox', 'sony', or 'poe2'
    league="Standard"    # Optional league filter
)
markets = api.get_current_markets()  # Fetch current data
```

### 2. Order Book Conversion (`src/pot/api_client.py`)

The API returns **aggregate hourly data** with ranges:
```json
{
  "market_id": "chaos|divine",
  "lowest_ratio": {"chaos": 0.01, "divine": 100},
  "highest_ratio": {"chaos": 0.015, "divine": 150},
  "lowest_stock": {"chaos": 50, "divine": 1},
  "highest_stock": {"chaos": 1000, "divine": 10}
}
```

The `OrderBookConverter` creates **synthetic discrete orders** from this:

**Strategy: `range` (default)**
- Creates 2 orders per currency direction:
  - One at lowest ratio (best price)
  - One at highest ratio (worst available price)

**Strategy: `single`**
- Creates 1 order at average ratio

**Strategy: `detailed`**
- Creates 3 orders: low, mid, high ratios

### 3. Inspection Tool (`inspect_api.py`)

Diagnostic script to view raw API data:
```bash
python inspect_api.py                    # Latest data
python inspect_api.py --timestamp 1734912000  # Historical data
```

Shows:
- OAuth authentication status
- Raw JSON response
- All available leagues and market counts
- Currency pairs available

### 4. Full Pipeline (`fetch_market_data.py`)

End-to-end workflow:
```bash
python fetch_market_data.py \
  --league "Standard" \
  --havecurrency chaos \
  --havecurrencyqty 100 \
  --wantcurrency divine \
  --strategy range \
  --inspect
```

This:
1. Fetches live market data from PoE API
2. Converts to order book CSV
3. Runs MILP optimization
4. Outputs optimal trade sequence

---

## Understanding PoE2 Leagues

### What You Saw in the API Response

At timestamp `1734912000`, the PoE2 realm returned:
- **Standard**: 860 markets
- **Hardcore**: 36 markets

### Important Context for PoE2 Early Access

During PoE2 early access, the league structure may differ from PoE1:

1. **"Standard" might BE the current softcore league**
   - In PoE1, "Standard" is the permanent league
   - In PoE2 early access, "Standard" could be the name of the current softcore league
   - Challenge leagues may not exist yet or may have different naming

2. **Check the current timestamp**
   - The API returns hourly snapshots
   - Different timestamps may show different league names
   - Use `--timestamp` or omit it for latest data

3. **Verify with PoE2 game client**
   - Check what your current league is called in-game
   - That's the name to use with `--league` parameter

### How to Find Your League

```bash
# See all available leagues in latest data
python inspect_api.py

# Look at the "UNIQUE LEAGUES FOUND" section
# Use the exact league name you play in
```

Then filter to your league:
```bash
python fetch_market_data.py --league "YourLeagueNameHere" ...
```

---

## Complete Usage Example

### Step 1: Verify Your Credentials

Check `.env` file:
```
POE_CLIENT_ID=ribeyemaker
POE_CLIENT_SECRET=WVYgMi4xlh0l
POE_REALM=poe2
POE_LEAGUE=
```

### Step 2: Inspect Available Data

```bash
python inspect_api.py
```

Look for:
- ✓ Successful authentication
- League names that match your game
- Currency pairs you want to trade

### Step 3: Run Optimization

If you play in "Standard" (current PoE2 softcore):
```bash
python fetch_market_data.py \
  --league "Standard" \
  --havecurrency chaos \
  --havecurrencyqty 1000 \
  --wantcurrency divine \
  --timesteps 10 \
  --window 10 \
  --startgold 1000000 \
  --strategy range \
  --inspect
```

### Step 4: Read Results

The output shows:
```
💰 Optimal divine: 8.42
   Starting with: 1000 chaos
   Effective rate: 0.0084 divine/chaos

📋 Trade sequence (3 trades):
  timestep  have     want      quantity  gold_spent
  1         chaos    exalted   500       1000
  2         exalted  divine    5         1000
  3         chaos    divine    3         1000
```

---

## Key Parameters Explained

### API Parameters
- `--league`: Filter to specific league (e.g., "Standard", "Hardcore")
- `--realm`: Game realm (pc/xbox/sony/poe2) - default: poe2
- `--timestamp`: Unix timestamp for historical data (omit for latest)

### Order Book Parameters
- `--strategy`: How to create orders from API ranges
  - `range`: Best + worst prices (most realistic)
  - `single`: Average price (simpler)
  - `detailed`: Low/mid/high (more granular)
- `--goldcost`: Fixed gold per trade (default: 1000)
- `--save-csv`: Where to save order book CSV

### Optimization Parameters
- `--havecurrency`: Starting currency (e.g., "chaos")
- `--havecurrencyqty`: How much you have (e.g., 100)
- `--wantcurrency`: Target currency (e.g., "divine")
- `--timesteps`: Number of trading rounds (default: 10)
- `--window`: Max trades per timestep (default: 10)
- `--startgold`: Starting gold (default: 1000000)
- `--solver`: Pyomo solver (default: appsi_highs)

### Control Flags
- `--fetch-only`: Just download data, don't optimize
- `--inspect`: Print detailed order book info

---

## How the Optimization Works

### 1. Graph Construction

Each order becomes a directed edge:
```
(chaos) --[ratio=0.01, stock=100, gold=1000]--> (divine)
```

### 2. MILP Model Variables

For each order at each timestep:
- `x[order, t]`: Binary decision (0 or 1) - do we make this trade?
- `quantity[order, t]`: Integer units traded
- `inventory[currency, t]`: How much of each currency we hold
- `gold[t]`: Remaining gold

### 3. Constraints

1. **Discrete trading**: Can only trade whole units
2. **Stock limits**: Can't exceed order stock
3. **Gold budget**: Each trade costs gold
4. **Window limits**: Max trades per timestep
5. **Conservation**: Can't create/destroy currency

### 4. Objective

Maximize: `inventory[target_currency, final_timestep]`

### 5. Solver

HiGHS (open-source MILP solver) finds the optimal solution in seconds.

---

## Troubleshooting

### "No module named 'dotenv'"
```bash
pip install -r requirements.txt
```

### "Failed to get OAuth token: 403 Forbidden"
1. Check `.env` has correct credentials
2. Regenerate client_secret if needed
3. Verify User-Agent header is set (already in code)

### "No market data found for league 'X'"
- League name is case-sensitive
- Run `inspect_api.py` to see exact league names
- Try omitting `--league` to see all leagues

### "No valid orders could be created"
- All markets had zero ratios (no trading activity)
- Try a different timestamp
- Check if currencies exist in that league

### Only seeing "Standard" and "Hardcore"
- This may be correct for PoE2 early access
- Verify your in-game league name
- "Standard" might be the current softcore league in PoE2

---

## Next Steps

### 1. Confirm Your League
Run in-game and check your current league name, then use that exact name with `--league`.

### 2. Test with Small Amounts
Start with small currency amounts to verify the optimization makes sense:
```bash
python fetch_market_data.py \
  --league "Standard" \
  --havecurrency chaos \
  --havecurrencyqty 10 \
  --wantcurrency divine \
  --inspect
```

### 3. Validate Results
- Check if recommended trades match actual game rates
- Verify gold costs are reasonable
- Ensure currencies exist in your league

### 4. Automate Data Fetching
The API returns hourly snapshots. You could:
- Set up a cron job to fetch data every hour
- Build historical database of rates
- Track market trends over time

### 5. Integrate with Trading Workflow
- Use the trade sequence as a guide
- Manually execute trades in-game
- Compare actual results vs predicted

---

## Technical Details

### Dependencies
- `pyomo`: MILP modeling framework
- `highspy`: Fast open-source MILP solver
- `networkx`: Graph data structures
- `pandas`: Data manipulation
- `requests`: HTTP API calls
- `python-dotenv`: Environment variable management

### Python Version
- **Required**: Python 3.11.x
- **Note**: Python 3.14 has numpy compatibility issues

### API Rate Limits
- GGG enforces dynamic rate limits
- Limits shown in response headers
- Script will fail with HTTP 429 if exceeded
- Be respectful with request frequency

### Data Freshness
- API provides hourly snapshots
- Omit `--timestamp` for most recent data
- Use timestamps for backtesting strategies

---

## Files You Can Modify

### `.env`
Your OAuth credentials and default settings:
```
POE_CLIENT_ID=ribeyemaker
POE_CLIENT_SECRET=WVYgMi4xlh0l
POE_REALM=poe2
POE_LEAGUE=Standard    # Set your default league here
```

### Generated Files
- `market_orderbook.csv`: Last fetched order book (gitignored)
- Any CSVs you create with `--save-csv`

### Code Files (Advanced)
- `src/pot/api_client.py`: Modify order generation strategies
- `src/pot/optimize.py`: Adjust optimization model
- `fetch_market_data.py`: Customize pipeline workflow

---

## Summary

You now have a complete system to:
1. ✅ Fetch live PoE2 market data via OAuth API
2. ✅ Convert aggregate API data into discrete order books
3. ✅ Run MILP optimization to find optimal trading paths
4. ✅ Generate actionable trade sequences

The "Standard" league you're seeing is likely the correct current PoE2 softcore league. Use that for your optimization, and compare results against your actual in-game trading experience.

**Quick start command:**
```bash
python fetch_market_data.py --league "Standard" --havecurrency chaos --havecurrencyqty 100 --wantcurrency divine --inspect
```
