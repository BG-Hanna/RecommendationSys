"""
app.py - Application factory. Run with:  python app.py   (or: flask --app app run)

Creates Flask, connects SQLite, creates the tables, loads the products and
builds the search engine once at start-up.
"""

import os
from pathlib import Path

from flask import Flask

from database.db import db
from database.models import Product
from database.seed import init_database
from algorithms.search import SearchEngine
from routes import bp

BASE_DIR = Path(__file__).resolve().parent


def format_dzd(value):
    """Jinja filter: 185000 -> '185 000 DZD'."""
    if value is None:
        return ""
    return f"{value:,} DZD".replace(",", " ")


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{(BASE_DIR / 'heating_plumbing.db').as_posix()}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    app.register_blueprint(bp)
    app.jinja_env.filters["dzd"] = format_dzd

    with app.app_context():
        init_database()
        products = [p.to_dict() for p in Product.query.order_by(Product.id).all()]
        app.extensions["search_engine"] = SearchEngine(products)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
