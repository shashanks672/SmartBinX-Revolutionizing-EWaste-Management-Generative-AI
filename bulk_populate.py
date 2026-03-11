#!/usr/bin/env python3
"""
bulk_populate.py
- Reads models_to_scrape.txt
- If you have ifixit_scraper.lookup_ifixit_and_cache it uses that.
- Otherwise it writes a simple template entry into smartbinx_full.db for each model.
"""
import time, json, sqlite3, re
from pathlib import Path
from datetime import datetime

MODELS_FILE = "models_to_scrape.txt"
DB_PATH = "smartbinx_full.db"
DELAY = 1.5  # seconds between items

# Try to import a real scraper if present
try:
    from ifixit_scraper import lookup_ifixit_and_cache
    HAVE_SCRAPER = True
except Exception:
    HAVE_SCRAPER = False

def normalize_name(s: str) -> str:
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()

def template_materials_for_model(name: str):
    low = name.lower()
    if any(k in low for k in ("iphone","galaxy","pixel","oneplus","xiaomi","oppo","vivo","nokia","realme","poco")):
        return {"Plastic":30.0,"Glass":20.0,"Aluminum":8.0,"Copper":12.0,"Lithium":5.0,"Gold":0.02,"Others":24.98}
    if any(k in low for k in ("macbook","dell","hp","lenovo","asus","acer","msi","surface")):
        return {"Plastic":25.0,"Aluminum":20.0,"Glass":5.0,"Copper":10.0,"Steel/Iron":10.0,"Lithium":6.0,"Others":24.0}
    if any(k in low for k in ("tv","bravia","oled","qled")):
        return {"Plastic":35.0,"Glass":25.0,"Aluminum":5.0,"Copper":8.0,"Steel/Iron":5.0,"Others":22.0}
    return {"Plastic":30.0,"Glass":10.0,"Metal":20.0,"Others":40.0}

def save_to_db(display_name, source, source_url, materials_dict, notes="", confidence=0.2):
    materials_json = json.dumps(materials_dict, ensure_ascii=False)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('ewaste_models')")
    cols = [r[1] for r in cur.fetchall()]
    now = datetime.utcnow().isoformat()
    values = {
        'display_name': display_name,
        'model_name_normalized': normalize_name(display_name),
        'source': source,
        'source_url': source_url,
        'materials_json': materials_json,
        'notes': notes,
        'confidence': confidence,
        'last_updated': now
    }
    insert_cols = []
    insert_vals = []
    for col in ['display_name','model_name_normalized','source','source_url','materials_json','notes','confidence','last_updated']:
        if col in cols:
            insert_cols.append(col)
            insert_vals.append(values[col])
    if not insert_cols:
        # if the table doesn't exist or has unexpected schema, try a safe fallback
        cur.execute("CREATE TABLE IF NOT EXISTS ewaste_models (id INTEGER PRIMARY KEY AUTOINCREMENT, display_name TEXT, model_name_normalized TEXT, source TEXT, source_url TEXT, materials_json TEXT, notes TEXT, confidence REAL, last_updated TEXT)")
        insert_cols = ['display_name','model_name_normalized','source','source_url','materials_json','notes','confidence','last_updated']
        insert_vals = [values[c] for c in insert_cols]
    sql = f"INSERT INTO ewaste_models ({', '.join(insert_cols)}) VALUES ({', '.join(['?']*len(insert_vals))})"
    cur.execute(sql, insert_vals)
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid

def fallback_lookup_and_save(model_name):
    materials = template_materials_for_model(model_name)
    notes = "Template fallback (no scraper available)"
    rowid = save_to_db(model_name, "template", "", materials, notes=notes, confidence=0.2)
    return {"id": rowid, "display_name": model_name, "source": "template", "materials": materials, "confidence": 0.2}

def main():
    p = Path(MODELS_FILE)
    if not p.exists():
        print("ERROR: models_to_scrape.txt not found. Create it first.")
        return
    models = [l.strip() for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f"Found {len(models)} models to process.")
    for model in models:
        print("\nProcessing:", model)
        try:
            if HAVE_SCRAPER:
                print(" -> using lookup_ifixit_and_cache from ifixit_scraper.py")
                res = lookup_ifixit_and_cache(model)
                if res is None:
                    print(" -> scraper returned None, falling back to template save")
                    res = fallback_lookup_and_save(model)
                else:
                    print(" -> scraper returned:", res.get("source"), "confidence:", res.get("confidence"))
            else:
                print(" -> no scraper module found; using template fallback")
                res = fallback_lookup_and_save(model)
                print(" -> saved as template, id:", res.get("id"))
        except Exception as e:
            print("ERROR processing model:", model, " — ", e)
        time.sleep(DELAY)

if __name__ == "__main__":
    main()
