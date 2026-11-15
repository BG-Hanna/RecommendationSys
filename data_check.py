import csv
from collections import Counter

rows = list(csv.DictReader(open("data/products.csv", encoding="utf-8")))
for col in ["type_produit", "type_energie", "materiau", "puissance_kw",
            "capacite_litres", "superficie_m2", "availability"]:
    filled = [r[col] for r in rows if r[col].strip()]
    print(f"\n{col}: {len(filled)}/{len(rows)} filled, {len(set(filled))} distinct values")
    print("  top:", Counter(filled).most_common(6))