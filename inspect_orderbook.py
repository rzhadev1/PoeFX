"""
Quick script to inspect the order book CSV and find suspicious orders.
"""

import pandas as pd
import sys

if len(sys.argv) > 1:
    csv_file = sys.argv[1]
else:
    csv_file = 'market_orderbook.csv'

print(f"Reading: {csv_file}")
df = pd.read_csv(csv_file)

print(f"\nTotal orders: {len(df)}")

# Show all unique currencies
have_currencies = set(df['have'].unique())
want_currencies = set(df['want'].unique())
all_currencies = sorted(have_currencies.union(want_currencies))

print(f"\nAll currencies ({len(all_currencies)}):")
for curr in all_currencies:
    print(f"  - {curr}")

# Find orders involving specific currencies
print("\n" + "="*70)
print("Looking for suspicious 'ancient-rib' orders:")
print("="*70)

ancient_orders = df[(df['have'] == 'ancient-rib') | (df['want'] == 'ancient-rib')]
if len(ancient_orders) > 0:
    print(ancient_orders.to_string(index=False))
else:
    print("No ancient-rib orders found")

# Show chaos→divine direct orders (if any)
print("\n" + "="*70)
print("Direct chaos → divine orders:")
print("="*70)
direct = df[(df['have'] == 'chaos') & (df['want'] == 'divine')]
if len(direct) > 0:
    print(direct.to_string(index=False))
    print(f"\nDirect conversion rate: {direct['ratio'].mean():.4f} divine per chaos")
else:
    print("No direct chaos→divine orders found (that's why optimizer used intermediate currency)")

# Show most common currency pairs
print("\n" + "="*70)
print("Most common currency pairs (top 20):")
print("="*70)
df['pair'] = df['have'] + ' → ' + df['want']
pair_counts = df['pair'].value_counts().head(20)
for pair, count in pair_counts.items():
    print(f"  {pair}: {count} orders")

# Show extreme ratios (suspicious data)
print("\n" + "="*70)
print("Suspiciously high ratios (>100):")
print("="*70)
high_ratio = df[df['ratio'] > 100].sort_values('ratio', ascending=False)
if len(high_ratio) > 0:
    print(high_ratio[['have', 'want', 'ratio', 'stock']].head(10).to_string(index=False))
else:
    print("None found")

print("\n" + "="*70)
print("Suspiciously low ratios (<0.001):")
print("="*70)
low_ratio = df[df['ratio'] < 0.001].sort_values('ratio')
if len(low_ratio) > 0:
    print(low_ratio[['have', 'want', 'ratio', 'stock']].head(10).to_string(index=False))
else:
    print("None found")
