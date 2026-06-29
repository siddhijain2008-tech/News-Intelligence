"""
News Intelligence Engine - Fixed & Complete
"""

import sqlite3, json, math, re, hashlib, datetime, urllib.request, html
import xml.etree.ElementTree as ET
import numpy as np
from collections import Counter
from bs4 import BeautifulSoup
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "data", "news.db")
VOCAB_PATH = os.path.join(BASE_DIR, "data", "vocab.json")

RSS_FEEDS = [
    ("Technology", "https://feeds.feedburner.com/TechCrunch"),
    ("Technology", "http://rss.cnn.com/rss/edition_technology.rss"),
    ("Business",   "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("World",      "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Science",    "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml"),
    ("AI",         "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("India",      "https://feeds.feedburner.com/ndtvnews-top-stories"),
]

# ── DB ───────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS articles (
        id        TEXT PRIMARY KEY,
        title     TEXT,
        url       TEXT,
        source    TEXT,
        category  TEXT,
        published TEXT,
        summary   TEXT,
        fetched_at TEXT
    );
    CREATE TABLE IF NOT EXISTS chunks (
        id         TEXT PRIMARY KEY,
        article_id TEXT,
        chunk_idx  INTEGER,
        text       TEXT,
        embedding  BLOB
    );
    CREATE TABLE IF NOT EXISTS interactions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id TEXT,
        action     TEXT,
        ts         TEXT
    );
    CREATE TABLE IF NOT EXISTS user_profile (
        key   TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    conn.commit()
    conn.close()

# ── RSS ──────────────────────────────────────────────────────────────────────

def fetch_rss(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None

def parse_rss(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            t = item.findtext("title","").strip()
            u = item.findtext("link","").strip()
            d = item.findtext("pubDate","") or ""
            desc = item.findtext("description","") or ""
            if t and u:
                items.append({"title":t,"url":u,"date":d,"summary":clean_html(desc)})
        if not items:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t = entry.findtext("{http://www.w3.org/2005/Atom}title","").strip()
                u = ""
                for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
                    if link.get("rel","alternate") == "alternate":
                        u = link.get("href",""); break
                    u = link.get("href", u)
                d = entry.findtext("{http://www.w3.org/2005/Atom}updated","")
                desc = entry.findtext("{http://www.w3.org/2005/Atom}summary","") or \
                       entry.findtext("{http://www.w3.org/2005/Atom}content","")
                if t and u:
                    items.append({"title":t,"url":u,"date":d,"summary":clean_html(desc)})
    except Exception:
        pass
    return items

def clean_html(raw):
    if not raw: return ""
    try:
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    except Exception:
        text = html.unescape(re.sub(r"<[^>]+>"," ",raw))
    return re.sub(r"\s+"," ",text).strip()

def article_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:16]

def ingest_feeds(feeds=None, max_per_feed=20):
    if feeds is None: feeds = RSS_FEEDS
    conn = get_db()
    new_articles = []
    for category, url in feeds:
        xml = fetch_rss(url)
        if not xml: continue
        items = parse_rss(xml)
        for item in items[:max_per_feed]:
            aid = article_id(item["url"])
            if conn.execute("SELECT 1 FROM articles WHERE id=?", (aid,)).fetchone():
                continue
            conn.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?)",
                (aid, item["title"], item["url"],
                 url.split("/")[2], category, item["date"],
                 item["summary"][:1000],
                 datetime.datetime.now(datetime.timezone.utc).isoformat()))
            conn.commit()
            text = item["title"] + ". " + item["summary"]
            new_articles.append((aid, text))
    conn.close()
    if new_articles:
        build_embeddings(new_articles)
    return len(new_articles)

# ── REINDEX: fix any articles missing embeddings ─────────────────────────────

def reindex_missing():
    """Find articles with no chunks and embed them."""
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id, a.title, a.summary FROM articles a
        WHERE a.id NOT IN (SELECT DISTINCT article_id FROM chunks)
    """).fetchall()
    conn.close()
    if not rows:
        return 0
    pairs = [(r["id"], (r["title"] or "") + ". " + (r["summary"] or "")) for r in rows]
    build_embeddings(pairs)
    return len(pairs)

# ── TF-IDF EMBEDDINGS ────────────────────────────────────────────────────────

STOPWORDS = set(
    "the a an and or but in on at to for of is are was were be been have has "
    "had do does did will would could should may might it its this that these "
    "those with from by about as said says new also just over after more than "
    "into their they them been being all one two three he she we you our your "
    "my his her its our can not no so up out if when who how what which while "
    "then there here each been very most than some any even such now us our "
    "both still only back well too however through between under before after "
    "us than re ve ll don isn didn wasn weren hasn haven hadn won can".split()
)

def tokenize(text):
    tokens = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [t for t in tokens if t not in STOPWORDS]

def load_vocab():
    try:
        with open(VOCAB_PATH) as f: return json.load(f)
    except Exception:
        return {"vocab":{}, "idf":{}, "df_counts":{}, "doc_count":0}

def save_vocab(v):
    with open(VOCAB_PATH,"w") as f: json.dump(v, f)

def chunk_text(text, size=120, overlap=20):
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i:i+size]))
        i += size - overlap
    return chunks or [text]

def build_embeddings(article_texts):
    state = load_vocab()
    vocab = state["vocab"]
    idf_counts = state.get("df_counts", {})
    doc_count = state["doc_count"]

    for aid, text in article_texts:
        for t in set(tokenize(text)):
            idf_counts[t] = idf_counts.get(t, 0) + 1
            if t not in vocab:
                vocab[t] = len(vocab)
        doc_count += 1

    total = max(doc_count, 1)
    idf = {w: math.log((total+1)/(c+1))+1 for w,c in idf_counts.items()}
    dim = len(vocab)

    conn = get_db()
    for aid, text in article_texts:
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            cid = f"{aid}_{idx}"
            if conn.execute("SELECT 1 FROM chunks WHERE id=?", (cid,)).fetchone():
                continue
            vec = np.zeros(dim, dtype=np.float32)
            tokens = tokenize(chunk)
            tf = Counter(tokens)
            total_t = max(len(tokens), 1)
            for w, cnt in tf.items():
                if w in vocab:
                    vec[vocab[w]] = (cnt/total_t) * idf.get(w, 1.0)
            norm = np.linalg.norm(vec)
            if norm > 0: vec /= norm
            conn.execute("INSERT OR IGNORE INTO chunks VALUES (?,?,?,?,?)",
                         (cid, aid, idx, chunk, vec.tobytes()))
        conn.commit()
    conn.close()

    state.update({"vocab":vocab,"idf":idf,"df_counts":idf_counts,"doc_count":doc_count})
    save_vocab(state)

def query_vector(text):
    state = load_vocab()
    vocab = state.get("vocab", {})
    idf   = state.get("idf", {})
    if not vocab: return None
    dim = len(vocab)
    vec = np.zeros(dim, dtype=np.float32)
    tokens = tokenize(text)
    tf = Counter(tokens)
    total_t = max(len(tokens), 1)
    for w, cnt in tf.items():
        if w in vocab:
            vec[vocab[w]] = (cnt/total_t) * idf.get(w, 1.0)
    norm = np.linalg.norm(vec)
    if norm > 0: vec /= norm
    return vec

# ── SEMANTIC SEARCH ──────────────────────────────────────────────────────────

def semantic_search(query, top_k=12, category=None):
    qvec = query_vector(query)
    if qvec is None: return []
    conn = get_db()
    dim = len(qvec)
    rows = conn.execute("""
        SELECT c.article_id, c.text, c.embedding,
               a.title, a.url, a.source, a.category, a.published, a.summary, a.fetched_at
        FROM chunks c JOIN articles a ON c.article_id = a.id
        WHERE (? IS NULL OR a.category = ?)
    """, (category, category)).fetchall()
    conn.close()

    now = datetime.datetime.now(datetime.timezone.utc)
    scored = {}
    for r in rows:
        try:
            evec = np.frombuffer(r["embedding"], dtype=np.float32)
            if len(evec) != dim: continue
            chunk_score = float(np.dot(qvec, evec))
        except Exception:
            continue

        aid = r["article_id"]
        # Title boost: if query terms appear in title, boost score
        title_lower = (r["title"] or "").lower()
        query_terms = set(tokenize(query))
        title_terms = set(tokenize(title_lower))
        title_overlap = len(query_terms & title_terms) / max(len(query_terms), 1)
        title_boost = 1.0 + 0.5 * title_overlap

        # Recency boost: articles fresher than 48h get a small lift
        try:
            fetched = datetime.datetime.fromisoformat(r["fetched_at"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=datetime.timezone.utc)
            hours_old = max((now - fetched).total_seconds() / 3600, 0)
            recency_boost = 1.0 + 0.15 * math.exp(-hours_old / 48)
        except Exception:
            recency_boost = 1.0

        final_score = chunk_score * title_boost * recency_boost

        if aid not in scored or final_score > scored[aid][0]:
            scored[aid] = (final_score, dict(r))

    results = sorted(scored.values(), key=lambda x: -x[0])
    out = []
    for score, r in results:
        if score > 0.02:   # lowered raw threshold; boosts handle quality
            r["score"] = round(score, 4)
            out.append(r)
        if len(out) >= top_k: break
    return out

# ── INTEREST VECTOR ──────────────────────────────────────────────────────────

def get_interest_vector():
    conn = get_db()
    row = conn.execute("SELECT value FROM user_profile WHERE key='interest_vector'").fetchone()
    conn.close()
    if row:
        return np.array(json.loads(row["value"]), dtype=np.float32)
    return None

def save_interest_vector(vec):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_profile VALUES ('interest_vector',?)",
                 (json.dumps(vec.tolist()),))
    conn.commit()
    conn.close()

def update_interest_vector(article_id, liked=True, lr=0.2):
    conn = get_db()
    rows = conn.execute("SELECT embedding FROM chunks WHERE article_id=?", (article_id,)).fetchall()
    conn.close()
    state = load_vocab()
    dim = len(state.get("vocab", {}))
    if dim == 0 or not rows: return
    vecs = []
    for r in rows:
        try:
            v = np.frombuffer(r["embedding"], dtype=np.float32)
            if len(v) == dim: vecs.append(v)
        except: pass
    if not vecs: return
    article_vec = np.mean(vecs, axis=0)
    norm = np.linalg.norm(article_vec)
    if norm > 0: article_vec /= norm
    iv = get_interest_vector()
    if iv is None or len(iv) != dim:
        iv = np.zeros(dim, dtype=np.float32)

    # Likes push interest vector more strongly than dislikes pull it away
    # This prevents a few dislikes from erasing accumulated interests
    effective_lr = lr if liked else lr * 0.4
    iv = iv + (effective_lr * article_vec if liked else -effective_lr * article_vec)
    norm = np.linalg.norm(iv)
    if norm > 0: iv /= norm
    save_interest_vector(iv)

def record_interaction(article_id, action):
    conn = get_db()
    conn.execute("INSERT INTO interactions (article_id, action, ts) VALUES (?,?,?)",
                 (article_id, action, datetime.datetime.now(datetime.timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    if action == "like":   update_interest_vector(article_id, liked=True)
    elif action == "dislike": update_interest_vector(article_id, liked=False)

# ── RECOMMENDED FEED ─────────────────────────────────────────────────────────

def recommended_feed(limit=30):
    iv = get_interest_vector()
    conn = get_db()
    # Wider pool so we have more to rank
    articles = conn.execute(
        "SELECT * FROM articles ORDER BY fetched_at DESC LIMIT 400"
    ).fetchall()
    # Count interactions to adapt interest weight dynamically
    interaction_count = conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE action IN ('like','dislike')"
    ).fetchone()[0]
    conn.close()

    state = load_vocab()
    dim = len(state.get("vocab", {}))
    now = datetime.datetime.now(datetime.timezone.utc)

    # The more interactions we have, the more we trust the interest vector
    # Cold start (0 interactions) → 20% interest / 80% freshness
    # Warm (50+ interactions)     → 80% interest / 20% freshness
    interest_weight = min(0.8, 0.2 + 0.012 * interaction_count)
    freshness_weight = 1.0 - interest_weight

    results = []
    for a in articles:
        a = dict(a)
        try:
            fetched = datetime.datetime.fromisoformat(a["fetched_at"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=datetime.timezone.utc)
            hours_old = max((now - fetched).total_seconds() / 3600, 0)
            # Sharper freshness decay: half-life ~18h
            freshness = math.exp(-hours_old / 18)
        except:
            freshness = 0.5

        interest = 0.0
        if iv is not None and dim > 0:
            try:
                c2 = sqlite3.connect(DB_PATH)
                chunk_rows = c2.execute(
                    "SELECT embedding FROM chunks WHERE article_id=?", (a["id"],)
                ).fetchall()
                c2.close()
                vecs = [np.frombuffer(r[0], dtype=np.float32) for r in chunk_rows
                        if r[0] and len(np.frombuffer(r[0], dtype=np.float32)) == dim]
                if vecs:
                    avg = np.mean(vecs, axis=0)
                    norm = np.linalg.norm(avg)
                    if norm > 0: avg /= norm
                    interest = max(0.0, float(np.dot(iv, avg)))  # clamp negatives
            except: pass

        a["rec_score"] = round(interest_weight * interest + freshness_weight * freshness, 4)
        results.append(a)

    results.sort(key=lambda x: -x["rec_score"])

    # Diversity cap: at most 40% of feed from any one category
    max_per_cat = max(3, int(limit * 0.4))
    cat_counts = Counter()
    diverse = []
    for a in results:
        cat = a.get("category", "")
        if cat_counts[cat] < max_per_cat:
            diverse.append(a)
            cat_counts[cat] += 1
        if len(diverse) >= limit:
            break

    # If diversity cap left us short, fill remainder from overflow
    if len(diverse) < limit:
        seen_ids = {a["id"] for a in diverse}
        for a in results:
            if a["id"] not in seen_ids:
                diverse.append(a)
            if len(diverse) >= limit:
                break

    return diverse[:limit]

# ── TREND ANALYSIS ───────────────────────────────────────────────────────────

def trend_analysis():
    conn = get_db()
    rows = conn.execute("SELECT title, summary, category, published FROM articles").fetchall()
    conn.close()
    cat_count = Counter()
    word_count = Counter()
    STOP = set("the a an and or but in on at to for of is are was were be been have has "
               "had do does did will would could should may might it its this that these "
               "those with from by about as an said says new also just over after more "
               "than into their they them their been being all one two three".split())
    for r in rows:
        cat_count[r["category"]] += 1
        text = (r["title"] or "") + " " + (r["summary"] or "")
        words = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", text.lower()) if w not in STOP]
        word_count.update(words)
    return {
        "category_distribution": dict(cat_count.most_common()),
        "top_keywords": dict(word_count.most_common(25)),
        "total_articles": sum(cat_count.values()),
    }

# ── EXTRACTIVE SUMMARY ───────────────────────────────────────────────────────

def extractive_summary(articles, max_sentences=6):
    all_text = " ".join((a.get("title","") + ". " + a.get("summary","")) for a in articles)
    sentences = re.split(r"(?<=[.!?])\s+", all_text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    word_freq = Counter(tokenize(all_text))
    total = sum(word_freq.values()) or 1
    def score(s):
        return sum(word_freq[w]/total for w in tokenize(s))
    top = sorted(sentences, key=score, reverse=True)[:max_sentences]
    return " ".join(s for s in sentences if s in top)

# ── SAVED / LIKED ARTICLES ───────────────────────────────────────────────────

def get_saved_articles():
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT a.* FROM articles a
        JOIN interactions i ON a.id = i.article_id
        WHERE i.action IN ('like','save')
        ORDER BY i.ts DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── USER PROFILE ─────────────────────────────────────────────────────────────

def get_user_profile():
    conn = get_db()
    row = conn.execute("SELECT value FROM user_profile WHERE key='profile'").fetchone()
    conn.close()
    if row:
        return json.loads(row["value"])
    return None

def save_user_profile(name, interests):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_profile VALUES ('profile',?)",
                 (json.dumps({"name": name, "interests": interests}),))
    conn.commit()
    conn.close()
    # Seed interest vector from chosen categories
    articles = conn.execute if False else None
    _seed_interest_from_categories(interests)

def _seed_interest_from_categories(interests):
    """Pre-warm interest vector by liking articles in chosen categories."""
    conn = get_db()
    for cat in interests:
        rows = conn.execute(
            "SELECT id FROM articles WHERE category=? LIMIT 3", (cat,)
        ).fetchall()
        for r in rows:
            update_interest_vector(r[0], liked=True, lr=0.1)
    conn.close()