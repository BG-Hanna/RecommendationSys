"""
routes.py - Flask routes (the only file that knows about HTTP).
All the intelligence lives in algorithms/ and evaluation/.
"""

from datetime import datetime
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from sqlalchemy import func

from algorithms.preprocessing import normalize_text, tokenize
from algorithms.query_expansion import ALL_METHODS, METHOD_LABELS
from algorithms.recommendations import recommend
from algorithms.search import make_budget, price_in_budget
from algorithms.vocabulary import load_vocabulary
from database.db import db
from database.models import Favorite, Product, SearchHistory, User, UserInterest
from evaluation.metrics import run_evaluation

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------- helpers
def get_engine():
    return current_app.extensions["search_engine"]


def login_required(view):
    """Only logged-in users can see the page. Users who have not finished
    onboarding are sent to the interests questionnaire first."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = db.session.get(User, session["user_id"]) if "user_id" in session else None
        if user is None:
            session.clear()
            flash("Connectez-vous pour continuer.", "info")
            return redirect(url_for("main.login"))
        if not user.onboarding_completed and request.endpoint != "main.onboarding":
            return redirect(url_for("main.onboarding"))
        g.user = user
        return view(*args, **kwargs)
    return wrapper


@bp.app_context_processor
def inject_globals():
    user = getattr(g, "user", None)
    liked = {f.product_id for f in user.favorites} if user else set()
    return {"current_user": user, "liked_ids": liked}


def popularity_counts():
    """How many users saved each product as a favourite."""
    rows = db.session.query(Favorite.product_id, func.count(Favorite.id)).group_by(Favorite.product_id).all()
    return dict(rows)


def user_context(user):
    """Everything the recommender needs to know about one user."""
    budget = make_budget(max_value=user.budget_max) if user.budget_max else None
    return {
        "interest_keys": user.interest_keys(),
        "liked_ids": [f.product_id for f in user.favorites],
        "recent_queries": [h.original_query for h in user.searches[-5:]],
        "budget": budget,
    }


def budget_from_request(args):
    def number(name):
        raw = args.get(name, "").strip()
        return int(raw) if raw.isdigit() else None
    return make_budget(number("min"), number("max"), number("exact"),
                       strict=args.get("strict", "1") == "1")


def category_summary(products):
    summary = {}
    for product in products:
        entry = summary.setdefault(product["category"],
                                   {"name": product["category"],
                                    "image_url": product["image_url"], "count": 0})
        entry["count"] += 1
    return sorted(summary.values(), key=lambda c: c["name"])


def log_search(user, query, expanded_terms):
    """Store a search, unless it is identical to the previous one (e.g. filter changes)."""
    last = SearchHistory.query.filter_by(user_id=user.id).order_by(SearchHistory.id.desc()).first()
    if last and last.original_query == query:
        return
    db.session.add(SearchHistory(user_id=user.id, original_query=query,
                                 expanded_query=", ".join(expanded_terms)))
    db.session.commit()


def save_interests(user, keys):
    user.interest_rows = [UserInterest(interest=key) for key in keys]


def safe_next(target):
    """Only redirect to a path of this site (protection against open redirects)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.favorites")


def registration_error(username, email, password, confirm):
    if len(username) < 3:
        return "Le nom d'utilisateur doit contenir au moins 3 caractères."
    if "@" not in email:
        return "Adresse e-mail invalide."
    if len(password) < 6:
        return "Le mot de passe doit contenir au moins 6 caractères."
    if password != confirm:
        return "Les mots de passe ne correspondent pas."
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return "Nom d'utilisateur ou e-mail déjà utilisé."
    return None


# ---------------------------------------------------------------- accounts
@bp.route("/")
def index():
    return redirect(url_for("main.home") if "user_id" in session else url_for("main.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        error = registration_error(username, email, password, request.form.get("confirm", ""))
        if error:
            flash(error, "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("main.onboarding"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and user.check_password(request.form.get("password", "")):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("main.home" if user.onboarding_completed else "main.onboarding"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("main.login"))


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    interests = load_vocabulary()["interests"]
    if request.method == "POST":
        selected = [key for key in request.form.getlist("interests") if key in interests]
        if not selected:
            flash("Choisissez au moins un centre d'intérêt.", "error")
        else:
            save_interests(g.user, selected)
            g.user.onboarding_completed = True
            db.session.commit()
            flash("Vos intérêts ont été enregistrés.", "success")
            return redirect(url_for("main.home"))
    return render_template("onboarding.html", interests=interests,
                           selected=g.user.interest_keys())


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    interests = load_vocabulary()["interests"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "interests":
            selected = [key for key in request.form.getlist("interests") if key in interests]
            if selected:
                save_interests(g.user, selected)
                flash("Intérêts mis à jour.", "success")
            else:
                flash("Choisissez au moins un centre d'intérêt.", "error")
        elif action == "budget":
            raw = request.form.get("budget_max", "").strip()
            g.user.budget_max = int(raw) if raw.isdigit() else None
            flash("Préférence de budget enregistrée.", "success")
        db.session.commit()
        return redirect(url_for("main.profile"))
    engine = get_engine()
    favorites = [engine.get(f.product_id) for f in g.user.favorites]
    return render_template("profile.html", interests=interests,
                           selected=g.user.interest_keys(), favorites=favorites)


# ---------------------------------------------------------------- shopping
@bp.route("/home")
@login_required
def home():
    engine = get_engine()
    popularity = popularity_counts()
    recommendations = recommend(engine, user_context(g.user), popularity, top_n=8)
    popular = sorted(engine.products, key=lambda p: (-popularity.get(p["id"], 0), p["id"]))[:6]
    return render_template("home.html", recommendations=recommendations, popular=popular,
                           categories=category_summary(engine.products))


@bp.route("/search")
@login_required
def search():
    engine = get_engine()
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    budget = budget_from_request(request.args)
    terms = []
    if query:
        eq, ranked = engine.search(query, "bm25", ALL_METHODS)   # customers use BM25
        results = engine.build_results(ranked, budget)
        terms = [row["term"] for row in eq.expansion_terms()]
        log_search(g.user, query, terms)
    else:
        results = engine.build_results([(i, None) for i in range(len(engine.products))], budget)
    if category:
        results = [r for r in results if r["product"]["category"] == category]
    categories = sorted({p["category"] for p in engine.products})
    return render_template("search.html", query=query, category=category, budget=budget,
                           results=results, terms=terms, categories=categories)


@bp.route("/product/<product_id>")
@login_required
def product_detail(product_id):
    engine = get_engine()
    product = engine.get(product_id)
    if product is None:
        abort(404)
    return render_template("product.html", product=product,
                           similar=engine.similar_products(product_id, 4))


@bp.route("/favorite/<product_id>", methods=["POST"])
@login_required
def toggle_favorite(product_id):
    if get_engine().get(product_id) is None:
        abort(404)
    favorite = Favorite.query.filter_by(user_id=g.user.id, product_id=product_id).first()
    if favorite:
        db.session.delete(favorite)
        flash("Retiré des favoris.", "info")
    else:
        db.session.add(Favorite(user_id=g.user.id, product_id=product_id))
        flash("Ajouté aux favoris.", "success")
    db.session.commit()
    return redirect(safe_next(request.form.get("next", "")))


@bp.route("/favorites")
@login_required
def favorites():
    engine = get_engine()
    products = [engine.get(f.product_id) for f in g.user.favorites]
    return render_template("favorites.html", products=[p for p in products if p])


@bp.route("/history")
@login_required
def history():
    rows = SearchHistory.query.filter_by(user_id=g.user.id).order_by(SearchHistory.id.desc()).all()
    return render_template("history.html", rows=rows)


@bp.route("/history/<int:entry_id>/repeat")
@login_required
def repeat_search(entry_id):
    entry = SearchHistory.query.filter_by(id=entry_id, user_id=g.user.id).first_or_404()
    return redirect(url_for("main.search", q=entry.original_query))


@bp.route("/history/clear", methods=["POST"])
@login_required
def clear_history():
    SearchHistory.query.filter_by(user_id=g.user.id).delete()
    db.session.commit()
    flash("Historique effacé.", "info")
    return redirect(url_for("main.history"))


@bp.route("/api/suggest")
@login_required
def suggest():
    """Autocomplete: product names, vocabulary terms and past searches while typing;
    recent searches and categories when the search bar is empty."""
    engine = get_engine()
    typed = request.args.get("q", "").strip()
    items = []
    if typed:
        typed_norm = normalize_text(typed)
        tokens = tokenize(typed)
        prefix = tokens[-1] if tokens else typed_norm
        for product in engine.products:
            if typed_norm in normalize_text(product["name"]):
                items.append({"label": product["name"], "value": product["name"], "kind": "Produit"})
        for term in sorted(t for t in engine.df if t.startswith(prefix))[:5]:
            items.append({"label": term, "value": term, "kind": "Terme"})
        for row in SearchHistory.query.filter_by(user_id=g.user.id).all():
            if typed_norm in normalize_text(row.original_query):
                items.append({"label": row.original_query, "value": row.original_query, "kind": "Historique"})
    else:
        for row in SearchHistory.query.filter_by(user_id=g.user.id).order_by(SearchHistory.id.desc()).limit(4):
            items.append({"label": row.original_query, "value": row.original_query, "kind": "Récent"})
        for category in sorted({p["category"] for p in engine.products})[:5]:
            items.append({"label": category, "value": category, "kind": "Catégorie"})
    return jsonify({"suggestions": items[:10]})


# ---------------------------------------------------------------- academic space
@bp.route("/research")
@login_required
def research():
    engine = get_engine()
    query = request.args.get("q", "").strip()
    model = request.args.get("model", "compare")
    methods = request.args.getlist("methods") if "methods" in request.args else list(ALL_METHODS)
    context = {"query": query, "model": model, "methods": methods, "eq": None,
               "tfidf_rows": [], "bm25_rows": [], "overlap": None,
               "all_methods": ALL_METHODS, "method_labels": METHOD_LABELS}
    if query:
        eq = engine.expand(query, methods)
        tfidf_rows = engine.build_results(engine.rank(engine.score(eq.weights, "tfidf")))[:5]
        bm25_rows = engine.build_results(engine.rank(engine.score(eq.weights, "bm25")))[:5]
        ids_a = {r["product"]["id"] for r in tfidf_rows}
        ids_b = {r["product"]["id"] for r in bm25_rows}
        union = ids_a | ids_b
        context.update(eq=eq, tfidf_rows=tfidf_rows, bm25_rows=bm25_rows,
                       overlap=len(ids_a & ids_b) / len(union) if union else 0.0)
    return render_template("research.html", **context)


@bp.route("/evaluation")
@login_required
def evaluation():
    return render_template("evaluation.html", report=run_evaluation(get_engine()))
