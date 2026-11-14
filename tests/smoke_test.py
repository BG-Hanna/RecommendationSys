"""
smoke_test.py - End-to-end checks of the whole application.

Run from the project folder:   python -m tests.smoke_test
It uses a temporary database, so your real data is never touched.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.preprocessing import identify_terms  # noqa: E402
from app import create_app  # noqa: E402
from database.models import Favorite, SearchHistory, User  # noqa: E402
from evaluation.metrics import precision_at_k, recall_at_k  # noqa: E402


def check(condition, message):
    status = "OK " if condition else "FAIL"
    print(f"[{status}] {message}")
    if not condition:
        raise SystemExit(1)


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp.name}"})
    client = app.test_client()

    # 1. Step 1 of the pipeline: query term identification (example from the exercise)
    terms = identify_terms("Je cherche une chaudière économique pour ma maison.")
    check(terms == ["chaudiere", "economique", "maison"], f"query terms identified: {terms}")

    # 2. Registration -> onboarding is required
    r = client.post("/register", data={"username": "ali", "email": "ali@mail.dz",
                                       "password": "secret1", "confirm": "secret1"})
    check(r.status_code == 302 and "/onboarding" in r.headers["Location"], "registration redirects to onboarding")
    check(client.get("/home").status_code == 302, "pages are locked before onboarding")

    # 3. Onboarding: choose interests (saved in the database)
    r = client.post("/onboarding", data={"interests": ["boilers", "radiators"]})
    check(r.status_code == 302, "onboarding accepted")
    with app.app_context():
        user = User.query.filter_by(username="ali").first()
        check(user.onboarding_completed and sorted(user.interest_keys()) == ["boilers", "radiators"],
              "interests saved in the database")

    # 4. Logout / login
    check(client.post("/logout").status_code == 302, "logout works")
    check(client.get("/home").status_code == 302, "pages are locked after logout")
    r = client.post("/login", data={"username": "ali", "password": "wrong"})
    check(r.status_code == 200, "wrong password is refused")
    r = client.post("/login", data={"username": "ali", "password": "secret1"})
    check(r.status_code == 302 and r.headers["Location"].endswith("/home"), "login works")

    # 5. Home page with recommendations based on interests
    page = client.get("/home").get_data(as_text=True)
    check("Recommandé pour vous" in page and "Chaudière" in page, "home shows interest-based recommendations")

    # 6. Search: BM25 ranking with expansion, history saved
    r = client.get("/search", query_string={"q": "chaudière économique"})
    body = r.get_data(as_text=True)
    check(r.status_code == 200 and "Chaudière" in body, "search returns boiler products")
    check("Termes ajoutés automatiquement" in body, "expanded terms are shown to the user")
    with app.app_context():
        check(SearchHistory.query.count() == 1, "search saved in history")

    # 7. Budget filter: maximum budget removes expensive products in strict mode
    r = client.get("/search", query_string={"q": "chaudière", "max": "150000", "strict": "1"})
    body = r.get_data(as_text=True)
    check("245 000 DZD" not in body and "185 000 DZD" not in body and "152 000 DZD" not in body,
          "strict maximum budget hides boilers above 150 000 DZD")
    check("98 000 DZD" in body, "affordable boiler (98 000 DZD) still shown under the maximum budget")

    # 8. Favorites: like a product, persisted in the database
    client.post("/favorite/P001", data={"next": "/search?q=chaudière"})
    with app.app_context():
        check(Favorite.query.filter_by(product_id="P001").count() == 1, "favourite saved in the database")
    check("Ajouté aux favoris" in client.get("/favorites").get_data(as_text=True)
          or "Chaudière gaz à condensation" in client.get("/favorites").get_data(as_text=True),
          "favourite appears on the favorites page")

    # 9. Recommendations evolve after a favourite (the liked product is not repeated)
    page = client.get("/home").get_data(as_text=True)
    check('href="/product/P001"' not in page.split("Recommandé pour vous")[1].split("Produits populaires")[0],
          "a liked product is not recommended again")

    # 10. Search history can be replayed
    with app.app_context():
        entry = SearchHistory.query.first()
    r = client.get(f"/history/{entry.id}/repeat")
    check(r.status_code == 302 and "/search" in r.headers["Location"], "history entry can be repeated")

    # 11. Autocomplete suggestions
    data = json.loads(client.get("/api/suggest", query_string={"q": "chau"}).get_data(as_text=True))
    check(len(data["suggestions"]) > 0, "autocomplete returns suggestions while typing")

    # 12. Product detail with similar products
    r = client.get("/product/P001")
    check(r.status_code == 200 and "Produits similaires" in r.get_data(as_text=True), "product page with similar products")

    # 13. Profile: update budget preference
    client.post("/profile", data={"action": "budget", "budget_max": "200000"})
    with app.app_context():
        check(User.query.filter_by(username="ali").first().budget_max == 200000, "budget preference saved")

    # 14. Research space: expansion inspector and TF-IDF vs BM25 comparison
    r = client.get("/research", query_string={"q": "chauffage central", "model": "compare"})
    body = r.get_data(as_text=True)
    check(r.status_code == 200 and "Query Expansion Inspector" in body and "TF-IDF + cosinus" in body and "BM25" in body,
          "research page shows the inspector and both models")

    # 15. Evaluation: Precision@5 and Recall@5 computed from the labelled test queries
    r = client.get("/evaluation")
    body = r.get_data(as_text=True)
    check(r.status_code == 200 and "eval-chart" in body, "evaluation page renders the chart")
    check(precision_at_k(["P1", "X", "P2", "X", "X"], {"P1", "P2"}) == 0.4, "precision formula is correct")
    check(recall_at_k(["P1", "X", "P2"], {"P1", "P2", "P3", "P4"}) == 0.5, "recall formula is correct")

    # 16. Every page renders without template errors
    anonymous = app.test_client()
    for path in ["/login", "/register"]:
        check(anonymous.get(path).status_code == 200, f"public page renders: {path}")
    for path in ["/profile", "/history", "/favorites", "/onboarding", "/home",
                 "/search", "/research?q=robinet&model=bm25", "/research?q=robinet&model=tfidf",
                 "/research?q=robinet", "/evaluation", "/product/P999"]:
        code = client.get(path).status_code
        expected = 404 if "P999" in path else 200
        check(code == expected, f"page renders ({code}): {path}")

    os.unlink(tmp.name)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
