# streamlit_app.py
"""
SmartBinX — Streamlit front-end for:
- image-based waste categorization using an optional ML model
- product -> material lookup (sqlite DB) and quick add

Place this file in the project root (same folder as `smartbinx_full.db` and `models/`).
Run:
    streamlit run streamlit_app.py
"""

import json
import sqlite3
import os
import re
import difflib
from datetime import datetime

# streamlit and optional ML imports
try:
    import streamlit as st
except Exception as e:
    raise RuntimeError("Streamlit is required to run this app. Install with: pip install streamlit") from e

# image & numeric libs
from PIL import Image, UnidentifiedImageError
import numpy as np
import requests  # used for building maps link

# --- Config / paths ---
DB_PATH = "smartbinx_full.db"
MODEL_PATH = os.path.join("models", "classifier_model.h5")
CLASS_MAP_PATH = os.path.join("models", "class_indices.json")

# --- Small metadata for classes (used for explanation/hazard/tips) ---
CLASS_METADATA = {
    "e-waste": {
        "display": "Electronic Waste (E-waste)",
        "hazard": "Hazardous",
        "explain": "Contains batteries, heavy metals and electronics — must not go to regular trash.",
        "tip": "Dispose through an e-waste collection center or authorized recycler.",
    },
    "plastic": {
        "display": "Plastic",
        "hazard": "Non-hazardous (Recyclable maybe)",
        "explain": "Household plastics; recycling depends on local rules and plastic type.",
        "tip": "Clean and place in proper recycling bin if accepted locally.",
    },
    "glass": {
        "display": "Glass",
        "hazard": "Non-hazardous (Recyclable)",
        "explain": "Glass is widely recyclable but broken glass should be handled carefully.",
        "tip": "Wrap broken glass and follow local recycling instructions.",
    },
    "metal": {
        "display": "Metal",
        "hazard": "Non-hazardous (Recyclable)",
        "explain": "Metals are recyclable and often valuable as scrap.",
        "tip": "Take to scrap yard or recycling center.",
    },
    "other": {
        "display": "Mixed / Unknown",
        "hazard": "Depends on composition",
        "explain": "Mixed materials — disposal depends on exact composition.",
        "tip": "Check local guidelines or take to a collection center.",
    },
}

# --- Utilities / DB helpers ---
def init_db():
    """Create DB table if doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()

def normalize_name(s: str) -> str:
    if not s:
        return ""
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()

def get_cached_model(model_query: str, fuzzy: bool = True, like_limit: int = 5):
    """
    Improved lookup:
      1) exact normalized match on model_name_normalized
      2) display_name LIKE '%query%' (case-insensitive)
      3) fuzzy matching on display_name (difflib)
    Returns: dict (same shape as before) or None
    """
    if not model_query or not model_query.strip():
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) exact normalized match
    norm = normalize_name(model_query)
    cur.execute(
        "SELECT id, display_name, source, source_url, materials_json, notes, confidence, last_updated "
        "FROM ewaste_models WHERE model_name_normalized = ? LIMIT 1",
        (norm,)
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return {
            "id": row[0],
            "display_name": row[1],
            "source": row[2],
            "source_url": row[3],
            "materials": json.loads(row[4]) if row[4] else {},
            "notes": row[5],
            "confidence": row[6],
            "last_updated": row[7]
        }

    # 2) display_name LIKE (case-insensitive)
    like_term = f"%{model_query}%"
    try:
        cur.execute(
            "SELECT id, display_name, source, source_url, materials_json, notes, confidence, last_updated "
            "FROM ewaste_models WHERE display_name LIKE ? COLLATE NOCASE LIMIT ?",
            (like_term, like_limit)
        )
        rows = cur.fetchall()
    except Exception:
        rows = []

    if rows:
        # try to return first non-template authoritative result
        for r in rows:
            if r[2] and r[2].lower() != "template":
                conn.close()
                return {
                    "id": r[0],
                    "display_name": r[1],
                    "source": r[2],
                    "source_url": r[3],
                    "materials": json.loads(r[4]) if r[4] else {},
                    "notes": r[5],
                    "confidence": r[6],
                    "last_updated": r[7]
                }
        # else fall back to first returned row
        r = rows[0]
        conn.close()
        return {
            "id": r[0],
            "display_name": r[1],
            "source": r[2],
            "source_url": r[3],
            "materials": json.loads(r[4]) if r[4] else {},
            "notes": r[5],
            "confidence": r[6],
            "last_updated": r[7]
        }

    # 3) fuzzy matching on display_name list (difflib)
    if fuzzy:
        cur.execute("SELECT display_name FROM ewaste_models")
        all_names = [r[0] for r in cur.fetchall() if r[0]]
        conn.close()
        if all_names:
            matches = difflib.get_close_matches(model_query, all_names, n=3, cutoff=0.6)
            if matches:
                # take the first match, fetch its full row
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, display_name, source, source_url, materials_json, notes, confidence, last_updated "
                    "FROM ewaste_models WHERE display_name = ? LIMIT 1",
                    (matches[0],)
                )
                r = cur.fetchone()
                conn.close()
                if r:
                    return {
                        "id": r[0],
                        "display_name": r[1],
                        "source": r[2],
                        "source_url": r[3],
                        "materials": json.loads(r[4]) if r[4] else {},
                        "notes": r[5],
                        "confidence": r[6],
                        "last_updated": r[7]
                    }

    return None

def insert_template_model(display_name: str, materials: dict, source="template", confidence=0.2, notes="Auto-created entry"):
    """Insert a new template entry for a device."""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ewaste_models (display_name, model_name_normalized, source, materials_json, notes, confidence, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (display_name, normalize_name(display_name), source, json.dumps(materials), notes, confidence, now)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

# initialize DB immediately
init_db()

# --- ML model loader (optional) ---
# page config must be called early
st.set_page_config(page_title="SmartBinX — E-Waste Analyzer", layout="wide")
st.title("♻️ SmartBinX — E-Waste Material Analyzer")
st.caption("Image classification + product material lookup")

model = None
idx_to_class = None
tf_available = False

def try_load_model():
    global model, idx_to_class, tf_available
    if model is not None:
        return
    try:
        import tensorflow as tf
        tf_available = True
        if os.path.exists(MODEL_PATH) and os.path.exists(CLASS_MAP_PATH):
            model = tf.keras.models.load_model(MODEL_PATH)
            with open(CLASS_MAP_PATH, "r") as f:
                class_map = json.load(f)
            # Build idx->class mapping in either mapping shape
            try:
                # if mapping is name->index
                idx_to_class = {int(v): k for k, v in class_map.items()}
            except Exception:
                # else assume index->name
                idx_to_class = {int(k): v for k, v in class_map.items()}
            st.success(f"✅ Model loaded: {os.path.basename(MODEL_PATH)}")
        else:
            st.info("No ML model files found in models/. App will use simple fallback heuristic.")
    except Exception as e:
        tf_available = False
        model = None
        idx_to_class = None
        st.warning("TensorFlow not available or model failed to load — running in fallback mode.")
        st.write("Model load error:", str(e))

# Attempt to load model
try_load_model()

# --- UI layout with two tabs: Categorize / Details ---
tabs = st.tabs(["1. Waste Categorization (image)", "2. Product → Materials (lookup)"])

# ----------------------------
# Tab 1: Waste Categorization
# ----------------------------
with tabs[0]:
    st.header("Waste categorization")
    st.write("Upload an image and the model will predict whether it's e-waste, plastic, etc.")
    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader("Upload waste image (jpg/png)", type=["jpg", "jpeg", "png"])
        if uploaded:
            try:
                img = Image.open(uploaded).convert("RGB")
            except UnidentifiedImageError:
                st.error("Failed to open image. Please upload a valid JPG/PNG.")
                st.stop()
            except Exception as e:
                st.error("Failed to open image: " + str(e))
                st.stop()

            st.image(img, caption="Uploaded image", use_column_width=True)

            # If we have an ML model, run inference; otherwise fallback
            if model is not None:
                try:
                    target_size = (224, 224)
                    img_resized = img.resize(target_size)
                    x = np.array(img_resized).astype("float32") / 255.0
                    x = np.expand_dims(x, axis=0)
                    preds = model.predict(x)
                    # normalize preds depending on shape
                    preds = np.asarray(preds[0] if (isinstance(preds, (list, tuple)) and len(preds) > 0 and np.ndim(preds[0]) in (1,)) else preds)
                    if preds.ndim == 2 and preds.shape[0] == 1:
                        preds = preds[0]
                    top_idx = int(np.argmax(preds))
                    top_prob = float(preds[top_idx])
                    label = idx_to_class.get(top_idx, str(top_idx)) if idx_to_class else str(top_idx)

                    # Pull metadata for this predicted label (fallback to 'other' if missing)
                    meta = CLASS_METADATA.get(label, CLASS_METADATA.get("other", {"display": label, "hazard": "Unknown", "explain": "", "tip": ""}))

                    # Friendly display block
                    st.markdown(f"### 🧩 Prediction: **{meta['display']}**  —  confidence **{top_prob:.2f}**")
                    st.write(f"**Hazard level:** {meta.get('hazard', 'Unknown')}")
                    st.write(f"**Explanation:** {meta.get('explain', '')}")
                    st.write(f"**Quick tip:** {meta.get('tip', '')}")

                    # Top-3
                    try:
                        top3_idx = np.argsort(preds)[-3:][::-1]
                        st.markdown("#### Top predictions")
                        for ii in top3_idx:
                            name = idx_to_class.get(int(ii), str(ii)) if idx_to_class else str(ii)
                            st.write(f"- {name}: {float(preds[int(ii)]):.3f}")
                    except Exception:
                        pass

                    # Google Maps quick search link for disposal centers; allow user to specify location to narrow
                    st.markdown("---")
                    st.subheader("Find nearby disposal centers 🌍")
                    location = st.text_input("Enter your city or postal code (optional):", value="")
                    maps_query = f"{meta['display']} recycling {location}".strip()
                    maps_url = "https://www.google.com/maps/search/" + requests.utils.quote(maps_query)
                    st.markdown(f"[🔍 Open Google Maps results for nearby centers]({maps_url})", unsafe_allow_html=True)

                except Exception as e:
                    st.error("Error during model inference: " + str(e))
            else:
                # fallback heuristic: size + color heuristics + show metadata
                st.info("No ML model — using simple fallback heuristic.")
                w, h = img.size
                arr = np.array(img).astype(float)
                mean = arr.mean(axis=(0, 1))
                messages = []
                # simple rules (very heuristic)
                if (w < 120 or h < 120):
                    messages.append("Small object — maybe battery / small e-waste (low confidence).")
                if mean[0] > mean[1] and mean[0] > mean[2]:
                    messages.append("Reddish/metal/board presence -> possible e-waste.")
                if mean[2] > mean[0] and mean[2] > mean[1]:
                    messages.append("Bluish tone — could be packaging or glass.")
                if not messages:
                    messages.append("Default fallback: classified as **e-waste** (demo mode).")
                # pick label from messages heuristic
                fallback_label = "e-waste"
                meta = CLASS_METADATA.get(fallback_label, CLASS_METADATA.get("other"))
                st.markdown(f"### 🧩 Prediction (fallback): **{meta['display']}**")
                st.write("Reasoning:")
                for m in messages:
                    st.write("- " + m)
                st.write(f"**Hazard level:** {meta.get('hazard')}")
                st.write(f"**Quick tip:** {meta.get('tip')}")
                st.markdown("---")
                location = st.text_input("Enter your city or postal code (optional):", value="")
                maps_query = f"{meta['display']} recycling {location}".strip()
                maps_url = "https://www.google.com/maps/search/" + requests.utils.quote(maps_query)
                st.markdown(f"[🔍 Open Google Maps results for nearby centers]({maps_url})", unsafe_allow_html=True)

    with col2:
        st.subheader("Quick tips & actions")
        st.write("""
        - If you trained your own ML model, put:
          - model file: `models/classifier_model.h5`
          - class map: `models/class_indices.json`
        - Use the **Product → Materials** tab to lookup or add device material breakdowns.
        """)
        if st.button("Reload model"):
            try_load_model()
            st.rerun()

# ----------------------------
# Tab 2: Product -> Materials
# ----------------------------
with tabs[1]:
    st.header("Product → Material composition")
    st.write("Search for a product (model name) and view estimated material percentages. Add new products if missing.")

    with st.form("lookup_form", clear_on_submit=False):
        product_input = st.text_input("Enter device model name (e.g. iPhone 12, Dell Inspiron 15)")
        submit = st.form_submit_button("Lookup")

    if submit:
        if not product_input or not product_input.strip():
            st.warning("Please type a product model name first.")
        else:
            product_input = product_input.strip()
            data = get_cached_model(product_input)
            if data:
                st.success(f"Found: **{data['display_name']}** (source: {data['source']})")
                if data.get("source_url"):
                    st.markdown(f"[View source]({data['source_url']})")
                st.write("Last updated:", data.get("last_updated"))
                st.write("Confidence:", data.get("confidence"))
                materials = data.get("materials") or {}
                if materials:
                    try:
                        import pandas as pd
                        df = pd.DataFrame(list(materials.items()), columns=["Material", "Percent"])
                        st.table(df)
                        st.bar_chart(df.set_index("Material"))
                    except Exception:
                        st.write(materials)
                else:
                    st.info("No materials recorded for this product.")
                if data.get("notes"):
                    st.markdown("**Notes:** " + str(data.get("notes")))
            else:
                # ==== REPLACED BLOCK: try online lookup via scraper_online.py ====
                st.info("Model not found in local database — searching online...")
                try:
                    from scraper_online import lookup_live
                except Exception as e:
                    lookup_live = None
                    st.write("Online lookup module not available:", str(e))

                if lookup_live:
                    with st.spinner("Fetching product details from iFixit... please wait"):
                        try:
                            live = lookup_live(product_input, do_cache=True)
                            # Validate live result: must be dict with materials and decent confidence and not a template fallback
                            credible = False
                            if isinstance(live, dict):
                                source = (live.get("source") or "").lower()
                                confidence = float(live.get("confidence") or 0.0)
                                # treat template fallback or low-confidence as "not found"
                                MIN_CONFIDENCE = 0.40
                                is_template = (source == "template") or (not live.get("source_url"))
                                if (not is_template) and (confidence >= MIN_CONFIDENCE) and live.get("materials"):
                                    credible = True

                            if credible:
                                st.success(f"Found online: {live.get('display_name', product_input)} (source: {live.get('source', 'online')})")
                                if live.get("source_url"):
                                    st.markdown(f"[View source]({live.get('source_url')})")
                                st.write("Confidence:", float(live.get("confidence") or 0.0))
                                if live.get("notes"):
                                    st.markdown("**Notes:** " + str(live.get("notes")))
                                materials = live.get("materials") or {}
                                try:
                                    import pandas as pd
                                    df = pd.DataFrame(list(materials.items()), columns=["Material", "Percent"])
                                    st.table(df)
                                    st.bar_chart(df.set_index("Material"))
                                except Exception:
                                    st.write(materials)
                            else:
                                st.info("No authoritative online teardown found for this model.")
                                st.write("You can add a trusted entry manually, or try a different search term (e.g., include 'Pro' / exact model).")
                        except Exception as e:
                            st.error("Online lookup failed: " + str(e))
                            st.write("You can add a template entry (quick) or paste exact material percentages below.")
                else:
                    st.info("Online lookup not available. You can add a template entry (quick) or paste exact material percentages below.")

                # Manual add fallback (same as before)
                with st.expander("Add this product (quick template)"):
                    default_materials = {
                        "Plastic": 30.0,
                        "Glass": 20.0,
                        "Aluminum": 8.0,
                        "Copper": 12.0,
                        "Lithium": 5.0,
                        "Others": 25.0
                    }
                    materials_text = st.text_area("Materials JSON (example):", value=json.dumps(default_materials, indent=2), height=160)
                    source_text = st.text_input("Source label (optional)", value="template")
                    confidence_val = st.number_input("Confidence (0..1)", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
                    add_btn = st.button("Add product to DB")
                    if add_btn:
                        try:
                            parsed = json.loads(materials_text)
                            inserted_id = insert_template_model(product_input, parsed, source=source_text or "template", confidence=confidence_val, notes="Added from Streamlit UI")
                            st.success(f"Added product with id {inserted_id}.")
                        except Exception as e:
                            st.error("Failed to parse JSON materials or insert: " + str(e))

    st.markdown("---")
    st.subheader("Browse recent DB entries")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT display_name, source, confidence, last_updated FROM ewaste_models ORDER BY last_updated DESC LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        if rows:
            st.table([{"Name": r[0], "Source": r[1], "Confidence": r[2], "Last updated": r[3]} for r in rows])
        else:
            st.info("Database empty — add entries using the form above or run the scraper/bulk importer.")
    except Exception as e:
        st.error("DB read error: " + str(e))

# Footer / helpful links
st.markdown("---")
st.markdown("**Developer notes**: ")
st.markdown("""
- To use a custom classifier: place `classifier_model.h5` and `class_indices.json` under `models/` and click *Reload model*.
- The product DB is `smartbinx_full.db` (SQLite). You can view/edit it with DB browser tools or via Python.
- If you run into missing packages (e.g. TensorFlow) either install locally or train via Colab then copy `models/` to this project.
""")