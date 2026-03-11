# streamlit_app_ml.py - Streamlit app that loads a Keras classifier if available
import streamlit as st
from PIL import Image
import numpy as np
import os, json

st.set_page_config(layout="wide", page_title="SmartBinX — ML Demo")
st.title("SmartBinX — ML Image Classifier (demo)")

MODEL_PATH = "models/classifier_model.h5"
model = None
class_indices = None

if os.path.exists(MODEL_PATH):
    st.info("Loading ML model...")
    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(MODEL_PATH)
        st.success("ML model loaded.")
        # attempt to read class indices saved alongside the model
        if os.path.exists("models/class_indices.json"):
            with open("models/class_indices.json","r",encoding="utf-8") as f:
                class_indices = json.load(f)
                # invert mapping
                idx_to_class = {int(v):k for k,v in class_indices.items()}
        else:
            idx_to_class = None
    except Exception as e:
        st.error("Failed to load model: " + str(e))
        model = None
else:
    st.warning("No ML model found at models/classifier_model.h5. Train one with ml/train.py or use Colab.")

uploaded = st.file_uploader("Upload an image of waste (jpg/png)", type=["jpg","jpeg","png"])
if uploaded:
    img = Image.open(uploaded).convert("RGB")
    st.image(img, caption="Uploaded image", use_column_width=False)
    if model:
        # preprocess like training
        img_resized = img.resize((224,224))
        x = np.array(img_resized) / 255.0
        x = np.expand_dims(x, axis=0)
        preds = model.predict(x)[0]
        top_idx = int(np.argmax(preds))
        top_prob = float(preds[top_idx])
        label = idx_to_class.get(top_idx) if idx_to_class else str(top_idx)
        st.write(f"Predicted: **{label}** (confidence {top_prob:.2f})")
        # show top-3
        top3 = sorted(list(enumerate(preds)), key=lambda x: x[1], reverse=True)[:3]
        st.write("Top 3 predictions:")
        for i,p in top3:
            l = idx_to_class.get(i) if idx_to_class else str(i)
            st.write(f"- {l}: {p:.3f}")
    else:
        st.info("No model loaded — showing fallback heuristic.")
        # fallback heuristic: simple color/size heuristic
        w,h = img.size
        if w<200 or h<200:
            st.write("Heuristic: small object — maybe e-waste / battery (low confidence).")
        else:
            st.write("Heuristic: default -> e-waste (demo mode).")

st.markdown("---")
st.markdown("**Notes:**\n- To train a model, place labeled folders under `data/train/<class>` and run `python3 ml/train.py`.\n- After training, the model will save to `models/classifier_model.h5` and this app will use it.")
