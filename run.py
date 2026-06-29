#!/usr/bin/env python3
"""
NewsIQ - News Intelligence System
Run: python3 run.py
Then open: http://localhost:5000
"""
import os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("""
╔══════════════════════════════════════════════════════╗
║           📡 NewsIQ — News Intelligence System       ║
╠══════════════════════════════════════════════════════╣
║  Phase 1: RSS Ingestion + Chunking                   ║
║  Phase 2: TF-IDF Embeddings + Semantic Search        ║
║  Phase 3: Swipeable Feed + Like/Dislike/Save         ║
║  Phase 4: Recommendation Engine (interest vector)    ║
║  Phase 5: Continuous Learning Loop                   ║
║  Phase 6: Trend Analysis + Keyword Cloud             ║
║  Phase 7: Extractive Summarization                   ║
╠══════════════════════════════════════════════════════╣
║  Open your browser → http://localhost:5000           ║
╚══════════════════════════════════════════════════════╝
""")

from engine import init_db
from seed import seed
init_db()
seed()

import os
port = int(os.environ.get("PORT", 5000))
app.run(debug=False, host="0.0.0.0", port=port, use_reloader=False)
