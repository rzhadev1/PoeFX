"""
Example script for fetching Path of Exile currency market data and running optimization.

This script demonstrates how to:
1. Fetch real market data from the PoE API
2. Convert it to an order book format
3. Run the optimization to find profitable trades
"""

import argparse
import sys
import os
from dotenv import load_dotenv

sys.path.append('src')

from pot.api_client import fetch_and_convert, PoECurrencyAPI
from pot.monad import Solver
from pot.optimize import order_book_to_digraph, optimal_conversion

# Load credentials from .env
load_dotenv()


def progress(message, percent=None):
    """Print progress message with optional percentage."""
    if percent is not None:
        sys.stdout.write(f'\r{message} {percent}%')
        sys.stdout.flush()
    else:
        print(message)


def main():
    parser = argparse.ArgumentParser(
        description='Fetch PoE market data and optimize currency conversion.'
    )

    # API parameters (credentials come from .env)
    parser.add_argument('--league', '-l', type=str, default=None,
                       help='League name filter (e.g., "Standard"). Leave empty for all leagues.')
    parser.add_argument('--realm', '-r', type=str, default=None,
                       choices=['pc', 'xbox', 'sony', 'poe2'],
                       help='Game realm (default: from .env or poe2)')
    parser.add_argument('--timestamp', '-t', type=int, default=None,
                       help='Unix timestamp for historical data (default: latest available)')

    # Order book generation
    parser.add_argument('--strategy', '-st', type=str, default='range',
                       choices=['range', 'single', 'detailed'],
                       help='Order generation strategy (default: range)')
    parser.add_argument('--goldcost', '-gc', type=int, default=1000,
                       help='Fixed gold cost per trade (default: 1000)')
    parser.add_argument('--save-csv', '-o', type=str, default='market_orderbook.csv',
                       help='Path to save order book CSV (default: market_orderbook.csv)')

    # Optimization parameters
    parser.add_argument('--havecurrency', '-have', type=str, default='chaos',
                       help='Currency to convert from (default: chaos)')
    parser.add_argument('--havecurrencyqty', '-hqty', type=int, default=100,
                       help='Amount of starting currency (default: 100)')
    parser.add_argument('--wantcurrency', '-want', type=str, default='divine',
                       help='Currency to convert to (default: divine)')
    parser.add_argument('--timesteps', '-ts', type=int, default=10,
                       help='Number of timesteps (default: 10)')
    parser.add_argument('--window', '-w', type=int, default=10,
                       help='Trading window size (default: 10)')
    parser.add_argument('--startgold', '-g', type=int, default=1000000,
                       help='Starting gold amount (default: 1000000)')
    parser.add_argument('--solver', '-s', type=str, default='appsi_highs',
                       help='Pyomo solver (default: appsi_highs)')

    # Control flags
    parser.add_argument('--fetch-only', action='store_true',
                       help='Only fetch and save market data, do not optimize')
    parser.add_argument('--inspect', action='store_true',
                       help='Print raw market data for inspection')

    args = parser.parse_args()

    # Get credentials from environment
    client_id = os.getenv('POE_CLIENT_ID')
    client_secret = os.getenv('POE_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("ERROR: Missing credentials!")
        print("Please set POE_CLIENT_ID and POE_CLIENT_SECRET in your .env file")
        sys.exit(1)

    # Use env defaults if not specified
    realm = args.realm or os.getenv('POE_REALM', 'poe2')
    league = args.league or os.getenv('POE_LEAGUE', None)

    # Use latest completed hour if timestamp not provided
    timestamp = args.timestamp
    if timestamp is None:
        timestamp = PoECurrencyAPI.get_latest_completed_hour_timestamp()

    # Step 1: Fetch market data (with progress indicators)
    progress("⏳ Fetching market data from API...", 10)

    try:
        df = fetch_and_convert(
            client_id=client_id,
            client_secret=client_secret,
            league=league,
            output_file=args.save_csv,
            realm=realm,
            gold_cost=args.goldcost,
            order_strategy=args.strategy,
            timestamp_id=timestamp
        )

        progress("✓ Market data fetched", 30)
        print()  # New line after progress

        if args.inspect:
            print("\n" + "=" * 70)
            print("ORDER BOOK PREVIEW")
            print("=" * 70)
            print(df.to_string())
            print("\n")
            print("Unique currencies:")
            unique_have = set(df['have'].unique())
            unique_want = set(df['want'].unique())
            all_currencies = unique_have.union(unique_want)
            for curr in sorted(all_currencies):
                print(f"  - {curr}")

    except Exception as e:
        print(f"\n\n❌ Error fetching market data: {e}")
        sys.exit(1)

    # Step 2: Run optimization (unless --fetch-only)
    if args.fetch_only:
        print(f"\n💾 Order book saved to: {args.save_csv}")
        print("   (Skipping optimization due to --fetch-only flag)")
        return

    # Convert to graph
    progress("⏳ Building market graph...", 40)
    try:
        market_graph = order_book_to_digraph(df)
        progress("✓ Graph built", 50)
        print()  # New line

        # Create portfolio
        from_portfolio = {args.havecurrency: args.havecurrencyqty}

        # Run optimization
        progress("⏳ Running MILP optimization...", 60)
        solution = (
            optimal_conversion(
                market_graph,
                from_portfolio,
                args.wantcurrency,
                args.timesteps,
                args.window,
                args.startgold
            ) >> Solver(args.solver)
        )

        progress("✓ Optimization complete", 90)
        print()  # New line

        if solution is None or solution.status is not None:
            print(f"\n❌ Optimization failed: {solution.status if solution else 'Unknown error'}")
            sys.exit(1)

        # Get results
        optimal_value, trades = solution()

        # Display results
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"\n💰 Optimal {args.wantcurrency}: {optimal_value:.2f}")
        print(f"   Starting with: {args.havecurrencyqty} {args.havecurrency}")
        print(f"   Effective rate: {optimal_value / args.havecurrencyqty:.4f} {args.wantcurrency}/{args.havecurrency}")

        if len(trades) > 0:
            print(f"\n📋 Trade sequence ({len(trades)} trades):")
            print("-" * 70)
            print(trades.to_string(index=False))
        else:
            print("\n⚠️  No trades recommended (direct hold may be optimal)")

        print("\n" + "=" * 70)
        print(f"💾 Order book saved to: {args.save_csv}")
        print("=" * 70 + "\n")

        progress("✓ Complete", 100)
        print()  # Final new line

    except Exception as e:
        print(f"\n\n❌ Optimization error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
