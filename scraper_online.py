# backend/scraper.py
import requests
from bs4 import BeautifulSoup
import time
import json
import sqlite3
import re
from datetime import datetime
from urllib.parse import quote_plus

DB_PATH = "smartbinx_full.db"
USER_AGENT = "SmartBinXBot/1.0 (+https://yourproject.example) ExampleContact: support@smartbinx.example"

# small helper to normalize model names
def normalize_name(s: str) -> str:
    return re.sub(r'[^a-z0-9 ]', '', (s or "").lower()).strip()

# basic heuristic to turn a set of component names or text into material percentages
def heuristic_material_estimate(text: str) -> dict:
    # very simple heuristics — tweak as needed
    text = text.lower()
    scores = {
        "plastic": 0,
        "glass": 0,
        "aluminum": 0,
        "copper": 0,
        "gold": 0,
        "silver": 0,
        "lithium": 0,
        "steel": 0,
        "others": 0
    }
    # keywords mapping (expand for better accuracy)
    keyword_map = {
        "plastic": ["plastic", "polymer"],
        "glass": ["glass", "screen"],
        "aluminum": ["aluminium", "aluminum", "frame"],
        "copper": ["copper", "coil", "wiring"],
        "gold": ["gold"],
        "silver": ["silver"],
        "lithium": ["lithium", "battery"],
        "steel": ["steel", "iron"],
    }
    for mat, kws in keyword_map.items():
        for kw in kws:
            if kw in text:
                scores[mat] += text.count(kw) * 1.0

    # baseline distribution if nothing found
    total = sum(scores.values())
    if total == 0:
        return {
            "Plastic": 30.0,
            "Glass": 20.0,
            "Aluminum": 8.0,
            "Copper": 12.0,
            "Lithium": 5.0,
            "Others": 25.0
        }
    # normalize to percentages
    pct = {k: (v / total) * 100.0 for k, v in scores.items()}
    # remove zero entries and group tiny ones into Others
    out = {}
    others = 0.0
    for k, v in pct.items():
        if v < 1.0:
            others += v
        else:
            out[k.capitalize()] = round(v, 2)
    if others > 0:
        out["Others"] = round(others, 2)
    return out

# insert optional caching to DB
def cache_lookup(display_name: str, materials: dict, source: str, source_url: str, confidence: float = 0.5, notes: str = "scraped"):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    # create table if needed (safe)
    cur.execute("""CREATE TABLE IF NOT EXISTS ewaste_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        display_name TEXT,
        model_name_normalized TEXT,
        source TEXT,
        source_url TEXT,
        materials_json TEXT,
        notes TEXT,
        confidence REAL,
        last_updated TEXT
    )""")
    cur.execute(
        "INSERT INTO ewaste_models (display_name, model_name_normalized, source, source_url, materials_json, notes, confidence, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (display_name, normalize_name(display_name), source, source_url, json.dumps(materials), notes, confidence, now)
    )
    conn.commit()
    newid = cur.lastrowid
    conn.close()
    return newid

# main function to search iFixit and parse page
def lookup_live(model_name: str, do_cache: bool = True, user_agent: str = USER_AGENT, pause: float = 0.8):
    """
    Lookup product by searching iFixit. Returns dict:
    {
      display_name, source, source_url, materials (dict), notes, confidence, cached (bool)
    }
    """
    if not model_name or not model_name.strip():
        return None

    query = quote_plus(model_name)
    search_url = f"https://www.ifixit.com/Search?query={query}"

    headers = {"User-Agent": user_agent}
    try:
        # fetch search results
        r = requests.get(search_url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return {"error": f"Search request failed: {e}"}

    # parse results page
    parser = "lxml"  # prefer lxml
    try:
        soup = BeautifulSoup(r.text, parser)
    except Exception:
        soup = BeautifulSoup(r.text, "html.parser")

    # Try to find first teardown link: iFixit uses links with '/Teardown/' in URL often
    link = None
    for a in soup.select("a"):
        href = a.get("href", "")
        text = (a.get_text() or "").strip()
        if "/Teardown/" in href and model_name.lower().split()[0] in text.lower():
            link = href
            break
    # fallback: take first search result card link
    if not link:
        # try common search result structure
        result_link = soup.select_one("a.result__link") or soup.select_one("a.thumbnail")
        if result_link:
            link = result_link.get("href")

    if not link:
        # no teardown found -> return template fallback
        materials = heuristic_material_estimate(model_name)
        return {
            "display_name": model_name,
            "source": "template",
            "source_url": "",
            "materials": materials,
            "notes": "Template fallback (no iFixit result)",
            "confidence": 0.2,
            "cached": False
        }

    # build absolute URL if needed
    if link.startswith("/"):
        link = "https://www.ifixit.com" + link

    # respect rate limiting / be polite
    time.sleep(pause)

    try:
        r2 = requests.get(link, headers=headers, timeout=15)
        r2.raise_for_status()
    except Exception as e:
        # failed to fetch teardown page -> fallback
        materials = heuristic_material_estimate(model_name)
        return {
            "display_name": model_name,
            "source": "ifixit",
            "source_url": link,
            "materials": materials,
            "notes": f"Failed to fetch teardown page: {e}",
            "confidence": 0.25,
            "cached": False
        }

    try:
        soup2 = BeautifulSoup(r2.text, parser)
    except Exception:
        soup2 = BeautifulSoup(r2.text, "html.parser")

    # Attempt 1 — look for explicit material or weight sections (ifixit sometimes lists materials)
    page_text = soup2.get_text(separator=" ").lower()

    # Heuristic: look for component/part names that hint materials
    # e.g., scan for words 'battery', 'glass', 'aluminum', 'copper', 'gold'
    materials = heuristic_material_estimate(page_text)

    # Better attempts (if teardown includes a parts list or table):
    # Look for a part list container (site-specific tuning)
    # Example: ifixit uses .parts-list or .teardown-steps etc. (subject to change)
    parts_text = ""
    for sel in ["ul.parts", ".parts-list", ".teardown__parts", ".teardown-steps", ".teardown-content"]:
        el = soup2.select_one(sel)
        if el:
            parts_text = el.get_text(" ")
            break
    if parts_text:
        materials = heuristic_material_estimate(parts_text)

    response = {
        "display_name": model_name,
        "source": "ifixit",
        "source_url": link,
        "materials": materials,
        "notes": "Parsed heuristically from iFixit teardown content",
        "confidence": 0.45,
        "cached": False
    }

    # optional cache
    if do_cache:
        try:
            cache_lookup(model_name, materials, "ifixit", link, confidence=response["confidence"], notes=response["notes"])
            response["cached"] = True
        except Exception:
            pass

    return response