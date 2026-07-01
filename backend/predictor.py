"""
Loads the trained ML model and exposes a predict() function.
"""

import os
import re
import joblib
import numpy as np

# Path to model file:
# backend/predictor.py -> billwise-ai/ml/expense_model.pkl
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "ml", "expense_model.pkl")
)

CLEAN_RE = re.compile(r'[^a-zA-Z0-9\s]')
WHITESPACE_RE = re.compile(r'\s+')

_pipeline = None


def clean_text(text: str) -> str:
    text = str(text or '').lower()
    text = CLEAN_RE.sub(' ', text)
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text


def extract_text_features(texts):
    """Extract meta features from text for the ML model."""
    features = []
    for text in texts:
        original = str(text or '')
        cleaned = clean_text(original)
        tokens = cleaned.split()
        word_count = len(tokens)
        avg_word_len = float(sum(len(token) for token in tokens)) / word_count if word_count else 0.0
        has_digit = int(bool(re.search(r'\d', original)))
        has_currency = int(bool(re.search(r'[\$₹£€]', original)))
        has_bill_term = int(bool(re.search(r'\b(bill|invoice|receipt|fare|ticket)\b', cleaned)))
        features.append([word_count, avg_word_len, has_digit, has_currency, has_bill_term])
    return np.asarray(features, dtype=np.float64)


def _load_model():
    """Load ML pipeline only once."""
    global _pipeline

    if _pipeline is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found:\n{MODEL_PATH}\n"
                "Run ml/train_model.py first."
            )

        _pipeline = joblib.load(MODEL_PATH)

    return _pipeline


def _get_probs(model, text: str):
    if hasattr(model, 'predict_proba'):
        return model.predict_proba([text])[0]

    if hasattr(model, 'decision_function'):
        scores = model.decision_function([text])[0]
        scores = np.asarray(scores, dtype=np.float64)
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / np.sum(exp_scores)

    return None


def _keyword_category_hint(text: str):
    kw_map = {
        'Groceries': [
            'grocery', 'supermarket', 'kirana', 'mart', 'groc', 'bread',
            'vegetable', 'fruit', 'dairy', 'produce', 'dmart', 'reliance fresh',
            'big bazaar', 'spencers', 'more', 'nature basket', 'cash carry',
            'hypermarket', 'super market', 'rice', 'dal', 'sugar', 'salt',
            'oil', 'milk', 'eggs', 'cheese', 'wheat', 'flour',
            'spices', 'tea', 'coffee', 'curd', 'yogurt', 'tomato',
            'onion', 'potato', 'garlic', 'cabbage', 'fresh produce', 'bulk',
            'kg quantity', 'store', 'provisions', 'shopping'
        ],
        'Food': [
            'restaurant', 'dinner', 'lunch', 'breakfast', 'cafe', 'hotel',
            'eatery', 'meal', 'snack', 'pizza', 'burger', 'coffee',
            'canteen', 'delivery', 'takeaway', 'table', 'waiter', 'dining',
            'dine', 'manchurian', 'biryani', 'naan', 'masala', 'paneer',
            'flavor', 'dessert', 'lassi', 'tandoori', 'kebab', 'cuisine',
            'food point', 'family restaurant'
        ],
        'Travel': [
            'uber', 'ola', 'taxi', 'cab', 'bus', 'train', 'flight', 'airport',
            'petrol', 'fuel', 'fare', 'ride', 'metro', 'railway', 'station'
        ],
        'Medical': [
            'pharmacy', 'chemist', 'hospital', 'clinic', 'medicine', 'medic',
            'prescription', 'doctor', 'health', 'dental', 'lab', 'chemists',
            'tablet', 'capsule', 'syrup', 'antibiotic', 'crocin', 'amoxicillin',
            'disprin', 'cetzine', 'pharmaceutical', 'medicament', 'drug',
            'apollo', 'medplus', 'diagnostic', 'pathology', 'injection'
        ],
        'Education': [
            'school', 'college', 'tuition', 'books', 'course', 'exam',
            'university', 'training', 'classes', 'academy', 'study', 'book',
            'textbook', 'sapna', 'engineering', 'mathematics', 'physics',
            'drawing', 'notebook', 'pen', 'pencil', 'stationery', 'bookstore',
            'educational', 'learning', 'institute', 'coaching', 'exam'
        ],
        'Electricity': [
            'electricity', 'power', 'electric', 'bill', 'energy', 'units',
            'consumed', 'charges', 'meter', 'utility', 'bright', 'home',
            'fuel', 'adjustment', 'duty', 'fixed', 'rent', 'payable'
        ],
        'Other': [
            'electricity', 'internet', 'recharge', 'mobile', 'utility',
            'rent', 'subscription', 'bill', 'tax', 'insurance', 'phone'
        ],
    }

    text = clean_text(text)
    scores = {category: 0 for category in kw_map}

    for category, keywords in kw_map.items():
        for kw in keywords:
            if kw in text:
                scores[category] += 1

    best_category = max(scores, key=scores.get)
    return best_category if scores[best_category] > 0 else None


def predict(text: str) -> dict:
    """
    Predict expense category from OCR bill text.

    Returns only normal Python values.
    This is important because Flask jsonify cannot safely return
    NumPy values such as np.str_ or np.float64.
    """

    if not text or not str(text).strip():
        return {
            "category": "Other",
            "confidence": 0.0,
            "all_scores": {}
        }

    text = str(text)
    cleaned = clean_text(text)

    try:
        model = _load_model()
        probs = _get_probs(model, cleaned)
        labels = model.classes_

        if probs is None:
            category = str(model.predict([cleaned])[0])
            return {
                "category": category,
                "confidence": 0.0,
                "all_scores": {category: 100.0}
            }

        best_idx = int(np.argmax(probs))
        model_category = str(labels[best_idx])
        model_confidence = float(probs[best_idx]) * 100

        all_scores = {
            str(labels[i]): round(float(probs[i]) * 100, 1)
            for i in range(len(labels))
        }

        hint_category = _keyword_category_hint(cleaned)
        category = model_category
        confidence = round(model_confidence, 1)

        if hint_category and hint_category != model_category:
            if confidence < 65.0 or model_category == 'Other':
                category = hint_category
                confidence = max(confidence, 75.0)
                all_scores[hint_category] = max(all_scores.get(hint_category, 0.0), confidence)

        if confidence < 55.0 and hint_category:
            category = hint_category
            confidence = max(confidence, 72.0)
            all_scores[hint_category] = max(all_scores.get(hint_category, 0.0), confidence)

        return {
            "category": category,
            "confidence": min(confidence, 100.0),
            "all_scores": all_scores
        }

    except Exception as error:
        print("\nPREDICTOR ERROR:", error)
        return {
            "category": "Other",
            "confidence": 0.0,
            "all_scores": {},
            "prediction_error": str(error)
        }
