"""
models.py - The database tables (SQLite through SQLAlchemy).

Users, Products, UserInterests, Favorites, SearchHistory.
"""

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    onboarding_completed = db.Column(db.Boolean, default=False, nullable=False)
    budget_max = db.Column(db.Integer, nullable=True)   # optional budget preference (DZD)

    interest_rows = db.relationship("UserInterest", backref="user",
                                    cascade="all, delete-orphan")
    favorites = db.relationship("Favorite", backref="user", cascade="all, delete-orphan")
    searches = db.relationship("SearchHistory", backref="user", cascade="all, delete-orphan",
                               order_by="SearchHistory.id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def interest_keys(self):
        return [row.interest for row in self.interest_rows]  # type: ignore

class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.String(300), nullable=False)
    brand = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Integer, nullable=False)        # DZD
    image_url = db.Column(db.String(200), nullable=False)
    availability = db.Column(db.String(60), nullable=False)
    # structured attributes (may be empty); used for display, filters and evaluation rules
    type_produit = db.Column(db.String(120), nullable=False, default="")
    type_energie = db.Column(db.String(30), nullable=False, default="")
    materiau = db.Column(db.String(120), nullable=False, default="")   # "acier émaillé, métal"
    puissance_kw = db.Column(db.Float, nullable=True)
    capacite_litres = db.Column(db.Float, nullable=True)
    superficie_m2 = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "category": self.category,
                "description": self.description, "keywords": self.keywords,
                "brand": self.brand, "price": self.price, "image_url": self.image_url,
                "availability": self.availability, "type_produit": self.type_produit,
                "type_energie": self.type_energie, "materiau": self.materiau,
                "puissance_kw": self.puissance_kw,
                "capacite_litres": self.capacite_litres, "superficie_m2": self.superficie_m2}


class UserInterest(db.Model):
    __tablename__ = "user_interests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    interest = db.Column(db.String(60), nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.String(10), db.ForeignKey("products.id"), nullable=False)


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_query = db.Column(db.String(300), nullable=False)
    expanded_query = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)