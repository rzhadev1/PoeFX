# Using the Path of Exile API Integration

This guide explains how to fetch live market data from the Path of Exile Currency Exchange API and use it with the optimization model.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Your OAuth credentials are already configured in `.env`:

```
POE_CLIENT_ID=ribeyemaker
POE_CLIENT_SECRET=VNgUNv17C2y8
POE_REALM=poe2
POE_LEAGUE=
```

**Note:** The `.env` file is in `.gitignore` to protect your credentials.

## Usage

### Step 1: Inspect Raw API Data

First, run the inspection script to see what data the API returns:

```bash
python inspect_api.py
```

This will:
- Authenticate with OAuth
- Fetch currency exchange data
- Display the raw JSON response
- Show summary statistics
- List all available leagues and currency pairs

**This is important!** Run this first and share the output so we can verify the API response structure matches our expectations.

### Step 2: Fetch and Optimize

Once we've confirmed the API data structure, use the main script:

```bash
# Basic usage - fetch all leagues and optimize
python fetch_market_data.py \
  --havecurrency chaos \
  --havecurrencyqty 100 \
  --wantcurrency divine

# Fetch for specific league
python fetch_market_data.py \
  --league "Standard" \
  --havecurrency chaos \
  --havecurrencyqty 100 \
  --wantcurrency divine

# Just fetch data without optimization
python fetch_market_data.py --fetch-only

# Inspect the order book after fetching
python fetch_market_data.py --inspect
```

### Available Options

#### API Options
- `--league`, `-l`: Filter by league name (default: all leagues)
- `--realm`, `-r`: Game realm - pc, xbox, sony, or poe2 (default: poe2)

#### Order Book Generation
- `--strategy`, `-st`: Order generation strategy
  - `range`: Create orders at lowest and highest ratios (default)
  - `single`: Create one order at average ratio
  - `detailed`: Create multiple orders across the range
- `--goldcost`, `-gc`: Fixed gold cost per trade (default: 1000)
- `--save-csv`, `-o`: Output CSV file path (default: market_orderbook.csv)

#### Optimization Options
- `--havecurrency`, `-have`: Starting currency (default: chaos)
- `--havecurrencyqty`, `-hqty`: Starting amount (default: 100)
- `--wantcurrency`, `-want`: Target currency (default: divine)
- `--timesteps`, `-ts`: Number of timesteps (default: 10)
- `--window`, `-w`: Trading window size (default: 10)
- `--startgold`, `-g`: Starting gold (default: 1000000)
- `--solver`, `-s`: Pyomo solver (default: appsi_highs)

#### Control Flags
- `--fetch-only`: Only fetch and save data, skip optimization
- `--inspect`: Print detailed order book information

## Order Generation Strategies

The API returns aggregate hourly data with ranges (lowest/highest ratio and stock). We convert this into discrete orders:

### `range` (default)
Creates 2 orders per direction per market:
- One at the lowest ratio (best price)
- One at the highest ratio (worst price)

### `single`
Creates 1 order per direction at the average ratio

### `detailed`
Creates 3 orders per direction:
- Low, mid, and high ratios

## Example Workflow

```bash
# 1. Inspect API data first
python inspect_api.py

# 2. Fetch data and run optimization
python fetch_market_data.py \
  --havecurrency chaos \
  --havecurrencyqty 1000 \
  --wantcurrency divine \
  --strategy range \
  --inspect

# 3. Review the results and trade sequence
```

## API Details

### Authentication
Uses OAuth 2.1 client_credentials grant:
- Scope: `service:cxapi`
- Tokens don't expire (can be revoked manually)

### Endpoint
```
GET https://api.pathofexile.com/currency-exchange/poe2
```

### Response Format
```json
{
  "next_change_id": 1234567890,
  "markets": [
    {
      "league": "Standard",
      "market_id": "chaos|divine",
      "volume_traded": {"chaos": 15000, "divine": 150},
      "lowest_stock": {"chaos": 50, "divine": 1},
      "highest_stock": {"chaos": 1000, "divine": 10},
      "lowest_ratio": {"chaos": 0.01, "divine": 100},
      "highest_ratio": {"chaos": 0.015, "divine": 150}
    }
  ]
}
```

### Rate Limits
- Enforced by GGG with dynamic limits
- Response headers include rate limit info
- Script will fail with HTTP 429 if exceeded

## Troubleshooting

### Missing Credentials
```
ERROR: Missing credentials!
```
Solution: Make sure `.env` exists with valid credentials

### No Market Data
```
ValueError: No market data found
```
Possible causes:
- Wrong league name
- No trading activity in the requested hour
- API returned empty response

### Authentication Failed
```
Failed to get OAuth token
```
Check:
- Credentials are correct in `.env`
- Network connection
- OAuth endpoint is accessible

## Next Steps

After running `inspect_api.py`, share the output so we can:
1. Verify the currency naming conventions
2. Confirm the data structure
3. Adjust the order generation strategy if needed
4. Map currency codes to full names if necessary
