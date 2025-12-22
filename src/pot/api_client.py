"""
Path of Exile Currency Exchange API Client

Fetches real-time market data from the official PoE API and converts it
into the format expected by the optimization model.
"""

import requests
import pandas as pd
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
import time


class PoECurrencyAPI:
    """Client for fetching Path of Exile currency exchange market data."""

    BASE_URL = "https://api.pathofexile.com"
    OAUTH_URL = "https://www.pathofexile.com/oauth/token"

    def __init__(self, client_id: str, client_secret: str, realm: str = "poe2", league: str = None):
        """
        Initialize the PoE Currency Exchange API client.

        :param client_id: OAuth client ID
        :param client_secret: OAuth client secret
        :param realm: Game realm ('pc', 'xbox', 'sony', 'poe2'). Default is 'poe2'
        :param league: Specific league name filter (e.g., 'Standard', current challenge league).
                       If None, will return all leagues from API response.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.realm = realm if realm != "pc" else None  # PC realm is default (None)
        self.league = league
        self.access_token = None
        self.token_expires_at = 0

    @staticmethod
    def get_latest_completed_hour_timestamp() -> int:
        """
        Calculate the Unix timestamp for the most recent completed hour.

        The API only provides historical data for completed hours.
        This function:
        1. Gets current UTC time
        2. Truncates to start of current hour (minutes/seconds = 0)
        3. Subtracts 1 hour to get the previous completed hour
        4. Returns as Unix integer timestamp

        :return: Unix timestamp (integer) for the latest completed hour
        """
        now_utc = datetime.now(timezone.utc)
        # Truncate to start of current hour
        current_hour = now_utc.replace(minute=0, second=0, microsecond=0)
        # Subtract 1 hour to get the previous completed hour
        from datetime import timedelta
        latest_completed_hour = current_hour - timedelta(hours=1)
        # Convert to Unix timestamp
        return int(latest_completed_hour.timestamp())

    def _get_access_token(self) -> str:
        """
        Get or refresh OAuth access token using client_credentials grant.

        :return: Access token string
        """
        # Check if we have a valid token
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # Request new token
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "service:cxapi"
        }

        headers = {
            "User-Agent": f"OAuth {self.client_id}/1.0.0 (contact: tedzbowles@gmail.com)"
        }

        try:
            response = requests.post(self.OAUTH_URL, data=data, headers=headers)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data["access_token"]
            # expires_in is null for client_credentials, but store anyway
            expires_in = token_data.get("expires_in")
            if expires_in:
                self.token_expires_at = time.time() + expires_in - 60  # 60s buffer
            else:
                # Token doesn't expire, set far future
                self.token_expires_at = time.time() + (365 * 24 * 60 * 60)

            return self.access_token

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get OAuth token: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with current access token."""
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": f"OAuth {self.client_id}/1.0.0 (contact: tedzbowles@gmail.com)"
        }

    def fetch_markets(self, timestamp_id: Optional[int] = None) -> Dict:
        """
        Fetch currency exchange market data from the API.

        :param timestamp_id: Unix timestamp for historical data.
                            If None, fetches first hour of history.
        :return: Raw API response as dictionary
        """
        # Construct URL: /currency-exchange[/<realm>][/<id>]
        url_parts = [self.BASE_URL, "currency-exchange"]
        if self.realm:
            url_parts.append(self.realm)
        if timestamp_id:
            url_parts.append(str(timestamp_id))

        url = "/".join(url_parts)

        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch market data: {e}")

    def get_current_markets(self, timestamp_id: Optional[int] = None) -> List[Dict]:
        """
        Fetch market data and filter by league if specified.

        :param timestamp_id: Unix timestamp for historical data
        :return: List of market dictionaries
        """
        data = self.fetch_markets(timestamp_id=timestamp_id)
        markets = data.get("markets", [])

        # Filter by league if specified
        if self.league:
            markets = [m for m in markets if m.get("league") == self.league]

        return markets


class OrderBookConverter:
    """Converts PoE API market data into order book format for optimization."""

    # Default gold cost for all trades
    DEFAULT_GOLD_COST = 1000

    def __init__(self, gold_cost: int = DEFAULT_GOLD_COST,
                 order_strategy: str = "range"):
        """
        Initialize the order book converter.

        :param gold_cost: Fixed gold cost per trade
        :param order_strategy: Strategy for generating orders:
            - 'range': Create orders at lowest and highest ratios
            - 'single': Create single order at average ratio
            - 'detailed': Create multiple orders across the range
        """
        self.gold_cost = gold_cost
        self.order_strategy = order_strategy

    def _parse_market_id(self, market_id: str) -> Tuple[str, str]:
        """
        Parse market_id into currency pair.

        :param market_id: Market ID like "chaos|divine"
        :return: Tuple of (currency1, currency2)
        """
        currencies = market_id.split("|")
        if len(currencies) != 2:
            raise ValueError(f"Invalid market_id format: {market_id}")
        return tuple(currencies)

    def _create_orders_from_market(self, market: Dict) -> List[Dict]:
        """
        Create synthetic orders from a single market entry.

        :param market: Market dictionary from API
        :return: List of order dictionaries
        """
        market_id = market.get("market_id")
        curr1, curr2 = self._parse_market_id(market_id)

        volume_traded = market.get("volume_traded", {})
        lowest_stock = market.get("lowest_stock", {})
        highest_stock = market.get("highest_stock", {})
        lowest_ratio = market.get("lowest_ratio", {})
        highest_ratio = market.get("highest_ratio", {})

        # Skip markets with no trading activity (zero ratios)
        if all(v == 0 for v in lowest_ratio.values()) and all(v == 0 for v in highest_ratio.values()):
            return []

        orders = []

        if self.order_strategy == "range":
            # Create orders at lowest and highest price points
            # For each currency as the "have" currency
            for have_curr in [curr1, curr2]:
                want_curr = curr2 if have_curr == curr1 else curr1

                if have_curr not in lowest_ratio or have_curr not in highest_ratio:
                    continue

                # Skip if this currency has zero ratio (no trading)
                low_r = float(lowest_ratio[have_curr])
                high_r = float(highest_ratio[have_curr])
                if low_r == 0 and high_r == 0:
                    continue

                # Order at lowest ratio (best price for buyer)
                if low_r > 0:
                    orders.append({
                        "have": have_curr,
                        "want": want_curr,
                        "ratio": low_r,
                        "stock": int(lowest_stock.get(have_curr, 1)),
                        "gold_cost": self.gold_cost
                    })

                # Order at highest ratio (worst price for buyer, but available)
                # Only add if different from lowest
                if high_r > 0 and high_r != low_r:
                    orders.append({
                        "have": have_curr,
                        "want": want_curr,
                        "ratio": high_r,
                        "stock": int(highest_stock.get(have_curr, 1)),
                        "gold_cost": self.gold_cost
                    })

        elif self.order_strategy == "single":
            # Create single order at average price
            for have_curr in [curr1, curr2]:
                want_curr = curr2 if have_curr == curr1 else curr1

                if have_curr not in lowest_ratio or have_curr not in highest_ratio:
                    continue

                avg_ratio = (float(lowest_ratio[have_curr]) +
                           float(highest_ratio[have_curr])) / 2
                avg_stock = (int(lowest_stock.get(have_curr, 1)) +
                           int(highest_stock.get(have_curr, 1))) / 2

                orders.append({
                    "have": have_curr,
                    "want": want_curr,
                    "ratio": avg_ratio,
                    "stock": int(avg_stock),
                    "gold_cost": self.gold_cost
                })

        elif self.order_strategy == "detailed":
            # Create multiple orders across the range (low, mid, high)
            for have_curr in [curr1, curr2]:
                want_curr = curr2 if have_curr == curr1 else curr1

                if have_curr not in lowest_ratio or have_curr not in highest_ratio:
                    continue

                low_ratio = float(lowest_ratio[have_curr])
                high_ratio = float(highest_ratio[have_curr])
                mid_ratio = (low_ratio + high_ratio) / 2

                low_stock = int(lowest_stock.get(have_curr, 1))
                high_stock = int(highest_stock.get(have_curr, 1))
                mid_stock = int((low_stock + high_stock) / 2)

                # Create 3 orders
                orders.append({
                    "have": have_curr,
                    "want": want_curr,
                    "ratio": low_ratio,
                    "stock": low_stock,
                    "gold_cost": self.gold_cost
                })
                orders.append({
                    "have": have_curr,
                    "want": want_curr,
                    "ratio": mid_ratio,
                    "stock": mid_stock,
                    "gold_cost": self.gold_cost
                })
                orders.append({
                    "have": have_curr,
                    "want": want_curr,
                    "ratio": high_ratio,
                    "stock": high_stock,
                    "gold_cost": self.gold_cost
                })

        return orders

    def markets_to_dataframe(self, markets: List[Dict]) -> pd.DataFrame:
        """
        Convert list of markets to order book DataFrame.

        :param markets: List of market dictionaries from API
        :return: DataFrame with columns [have, want, ratio, stock, gold_cost]
        """
        all_orders = []

        for market in markets:
            try:
                orders = self._create_orders_from_market(market)
                all_orders.extend(orders)
            except Exception as e:
                print(f"Warning: Failed to process market {market.get('market_id')}: {e}")
                continue

        if not all_orders:
            raise ValueError("No valid orders could be created from market data")

        df = pd.DataFrame(all_orders)
        return df

    def save_to_csv(self, markets: List[Dict], filepath: str) -> pd.DataFrame:
        """
        Convert markets to DataFrame and save to CSV.

        :param markets: List of market dictionaries
        :param filepath: Path to save CSV file
        :return: The created DataFrame
        """
        df = self.markets_to_dataframe(markets)
        df.to_csv(filepath, index=False)
        print(f"Saved {len(df)} orders to {filepath}")
        return df


def fetch_and_convert(client_id: str,
                     client_secret: str,
                     league: str = None,
                     output_file: str = "market_orderbook.csv",
                     realm: str = "poe2",
                     gold_cost: int = 1000,
                     order_strategy: str = "range",
                     timestamp_id: Optional[int] = None) -> pd.DataFrame:
    """
    Convenience function to fetch market data and convert to order book CSV.

    :param client_id: PoE OAuth client ID
    :param client_secret: PoE OAuth client secret
    :param league: League name filter (e.g., current challenge league, 'Standard').
                   If None, includes all leagues.
    :param output_file: Path to save CSV file
    :param realm: Game realm ('pc', 'xbox', 'sony', 'poe2')
    :param gold_cost: Fixed gold cost per trade
    :param order_strategy: Order generation strategy ('range', 'single', 'detailed')
    :param timestamp_id: Unix timestamp for historical data (None = most recent)
    :return: DataFrame of order book
    """
    # Fetch market data
    api = PoECurrencyAPI(client_id, client_secret, realm=realm, league=league)
    markets = api.get_current_markets(timestamp_id=timestamp_id)

    if not markets:
        league_msg = f"league '{league}'" if league else "any league"
        raise ValueError(f"No market data found for {league_msg}")

    league_msg = f"league '{league}'" if league else "all leagues"
    print(f"Fetched {len(markets)} markets for {league_msg}")

    # Convert to order book
    converter = OrderBookConverter(gold_cost=gold_cost, order_strategy=order_strategy)
    df = converter.save_to_csv(markets, output_file)

    return df
