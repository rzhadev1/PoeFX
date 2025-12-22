"""
Simple script to inspect raw API data from the PoE Currency Exchange API.
Run this first to see what data is actually returned by the API.
"""

import sys
import os
import json
from dotenv import load_dotenv

sys.path.append('src')
from pot.api_client import PoECurrencyAPI

# Load credentials from .env file
load_dotenv()

CLIENT_ID = os.getenv('POE_CLIENT_ID')
CLIENT_SECRET = os.getenv('POE_CLIENT_SECRET')
REALM = os.getenv('POE_REALM', 'poe2')
LEAGUE = os.getenv('POE_LEAGUE')  # Can be None/empty

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Missing credentials!")
    print("Please set POE_CLIENT_ID and POE_CLIENT_SECRET in your .env file")
    sys.exit(1)

print("=" * 80)
print("Path of Exile Currency Exchange API Inspector")
print("=" * 80)
print(f"\nRealm: {REALM}")
print(f"League filter: {LEAGUE if LEAGUE else '(all leagues)'}")
print(f"Client ID: {CLIENT_ID}")
print("\n" + "=" * 80)

# Create API client
api = PoECurrencyAPI(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    realm=REALM,
    league=LEAGUE
)

print("\n[1/2] Authenticating with OAuth...")
try:
    token = api._get_access_token()
    print(f"✓ Successfully obtained access token: {token[:20]}...")
except Exception as e:
    print(f"✗ Failed to get access token: {e}")
    sys.exit(1)

print("\n[2/2] Fetching currency exchange data...")
try:
    data = api.fetch_markets()
    print(f"✓ Successfully fetched data")
except Exception as e:
    print(f"✗ Failed to fetch data: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("RAW API RESPONSE")
print("=" * 80)
print(json.dumps(data, indent=2))

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"next_change_id: {data.get('next_change_id')}")
print(f"Total markets: {len(data.get('markets', []))}")

if data.get('markets'):
    print("\n" + "-" * 80)
    print("MARKET DETAILS")
    print("-" * 80)

    for i, market in enumerate(data['markets'][:5], 1):  # Show first 5
        print(f"\n[Market {i}]")
        print(f"  League: {market.get('league')}")
        print(f"  Market ID: {market.get('market_id')}")
        print(f"  Volume Traded: {market.get('volume_traded')}")
        print(f"  Lowest Stock: {market.get('lowest_stock')}")
        print(f"  Highest Stock: {market.get('highest_stock')}")
        print(f"  Lowest Ratio: {market.get('lowest_ratio')}")
        print(f"  Highest Ratio: {market.get('highest_ratio')}")

    if len(data['markets']) > 5:
        print(f"\n... and {len(data['markets']) - 5} more markets")

print("\n" + "=" * 80)
print("UNIQUE LEAGUES FOUND")
print("=" * 80)
leagues = set(m.get('league') for m in data.get('markets', []))
for league in sorted(leagues):
    count = sum(1 for m in data['markets'] if m.get('league') == league)
    print(f"  {league}: {count} markets")

print("\n" + "=" * 80)
print("SAMPLE MARKET IDS (Currency Pairs)")
print("=" * 80)
market_ids = set(m.get('market_id') for m in data.get('markets', []))
for mid in sorted(list(market_ids)[:20]):  # Show first 20
    print(f"  {mid}")
if len(market_ids) > 20:
    print(f"  ... and {len(market_ids) - 20} more pairs")

print("\n" + "=" * 80)
print("\nDone! Use this information to understand the API response structure.")
print("Next: Run fetch_market_data.py to convert this into an order book.")
