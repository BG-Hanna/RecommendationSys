"""
seed.py - Creates the tables and loads data/products.csv the first time.

Run manually with:  python -m database.seed
(The application also does this automatically at start-up.)
"""

import csv
from pathlib import Path

from database.db import db
from database.models import Product

CSV_FILE = Path(__file__).resolve().parent.parent / "data" / "products.csv"


def load_products_from_csv(path=CSV_FILE):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def seed_products():
    """Insert the products only if the table is empty. Returns the number inserted."""
    if Product.query.first() is not None:
        return 0
    rows = load_products_from_csv()
    for row in rows:
        db.session.add(Product(
            id=row["id"], name=row["name"], category=row["category"],
            description=row["description"], keywords=row["keywords"], brand=row["brand"],
            price=int(row["price"]), image_url=row["image_url"],
            availability=row["availability"],
        ))
    db.session.commit()
    return len(rows)


def init_database():
    """Create all tables and seed the product catalogue."""
    db.create_all()
    return seed_products()


if __name__ == "__main__":
    from app import create_app

    application = create_app()
    with application.app_context():
        print(f"{Product.query.count()} produits disponibles dans la base.")
