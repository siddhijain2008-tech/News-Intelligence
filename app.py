import json, datetime, threading
from flask import Flask, render_template, request, jsonify, redirect, url_for
from engine import (
    init_db, ingest_feeds, reindex_missing, semantic_search, recommended_feed,
    trend_analysis, extractive_summary, record_interaction, get_db,
    get_saved_articles, get_user_profile, save_user_profile
)

app = Flask(__name__, template_folder="templates")
_started = False

@app.before_request
def startup():
    global _started
    if _started: return
    _started = True
    init_db()
    from seed import seed
    seed()
    threading.Thread(target=reindex_missing, daemon=True).start()
    threading.Thread(target=ingest_feeds, daemon=True).start()

def get_articles(limit=50, category=None):
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM articles WHERE category=? ORDER BY fetched_at DESC LIMIT ?",
            (category, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_categories():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT category FROM articles ORDER BY category").fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_stats():
    conn = get_db()
    total  = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    likes  = conn.execute("SELECT COUNT(*) FROM interactions WHERE action='like'").fetchone()[0]
    saves  = conn.execute("SELECT COUNT(*) FROM interactions WHERE action='save'").fetchone()[0]
    conn.close()
    return {"articles": total, "chunks": chunks, "likes": likes, "saves": saves}

# ── ONBOARDING ───────────────────────────────────────────────────────────────

@app.route("/onboarding", methods=["GET","POST"])
def onboarding():
    if request.method == "POST":
        name = request.form.get("name","User").strip() or "User"
        interests = request.form.getlist("interests")
        save_user_profile(name, interests)
        return redirect(url_for("index"))
    categories = ["AI", "Technology", "Business", "Science", "World", "India",
                  "Sports", "Health", "Politics", "Environment"]
    return render_template("onboarding.html", categories=categories)

# ── FEED ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    profile = get_user_profile()
    if not profile:
        return redirect(url_for("onboarding"))
    category = request.args.get("category")
    feed = recommended_feed(40)
    if category:
        feed = [a for a in feed if a.get("category") == category]
    if not feed:
        feed = get_articles(40, category)
    categories = get_categories()
    stats = get_stats()
    return render_template("index.html", articles=feed, categories=categories,
                           selected_category=category, stats=stats, profile=profile)

# ── SEARCH ───────────────────────────────────────────────────────────────────

@app.route("/search")
def search():
    query    = request.args.get("q","").strip()
    category = request.args.get("category")
    results  = semantic_search(query, top_k=15, category=category or None) if query else []
    return render_template("search.html", query=query, results=results,
                           categories=get_categories(),
                           selected_category=category, stats=get_stats(),
                           profile=get_user_profile())

# ── TRENDS ───────────────────────────────────────────────────────────────────

@app.route("/trends")
def trends():
    return render_template("trends.html", data=trend_analysis(),
                           stats=get_stats(), profile=get_user_profile())

# ── DIGEST ───────────────────────────────────────────────────────────────────

@app.route("/summary")
def summary():
    category = request.args.get("category")
    articles = get_articles(30, category)
    digest   = extractive_summary(articles) if articles else "No articles yet."
    return render_template("summary.html", digest=digest, articles=articles[:12],
                           categories=get_categories(), selected_category=category,
                           stats=get_stats(), profile=get_user_profile())

# ── SAVED ────────────────────────────────────────────────────────────────────

@app.route("/saved")
def saved():
    articles = get_saved_articles()
    return render_template("saved.html", articles=articles,
                           stats=get_stats(), profile=get_user_profile())

# ── PROFILE ──────────────────────────────────────────────────────────────────

@app.route("/profile")
def profile_page():
    profile = get_user_profile()
    conn = get_db()
    liked = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE action='like'").fetchone()[0]
    disliked = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE action='dislike'").fetchone()[0]
    saved = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE action='save'").fetchone()[0]
    recent = conn.execute("""
        SELECT a.title, a.category, i.action, i.ts
        FROM interactions i JOIN articles a ON i.article_id = a.id
        ORDER BY i.ts DESC LIMIT 10
    """).fetchall()
    conn.close()
    return render_template("profile.html", profile=profile,
                           liked=liked, disliked=disliked, saved=saved,
                           recent=[dict(r) for r in recent],
                           stats=get_stats())

# ── APIs ─────────────────────────────────────────────────────────────────────

@app.route("/api/interact", methods=["POST"])
def interact():
    data   = request.json or {}
    aid    = data.get("article_id")
    action = data.get("action")
    if not aid or action not in ("like","dislike","save"):
        return jsonify({"error":"bad request"}), 400
    record_interaction(aid, action)
    return jsonify({"ok": True})

@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    def bg():
        n = ingest_feeds()
        reindex_missing()
        print(f"[ingest] {n} new articles")
    threading.Thread(target=bg, daemon=True).start()
    return jsonify({"ok": True, "message": "Fetching news in background…"})

@app.route("/api/reindex", methods=["POST"])
def api_reindex():
    def bg():
        n = reindex_missing()
        print(f"[reindex] fixed {n} articles")
    threading.Thread(target=bg, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/reset_profile", methods=["POST"])
def reset_profile():
    conn = get_db()
    conn.execute("DELETE FROM user_profile WHERE key='profile'")
    conn.execute("DELETE FROM user_profile WHERE key='interest_vector'")
    conn.commit()
    conn.close()
    return redirect(url_for("onboarding"))

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
