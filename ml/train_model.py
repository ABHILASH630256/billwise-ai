"""
BillWise AI — ML Model Trainer
Trains a robust expense category classifier on expense_dataset.csv.
Supports standard TF-IDF + Logistic Regression and a large-scale
HashingVectorizer + SGDClassifier option for scaling to more data.
"""

import argparse
import csv
import os
import re
from collections import Counter

import joblib
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'expense_dataset.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'expense_model.pkl')

CLEAN_RE = re.compile(r'[^a-zA-Z0-9\s]')
WHITESPACE_RE = re.compile(r'\s+')

CATEGORIES = ['Groceries', 'Food', 'Travel', 'Medical', 'Education', 'Electricity', 'Other']


def clean_text(text: str) -> str:
    text = str(text or '').lower()
    text = CLEAN_RE.sub(' ', text)
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text


class TextFeatureExtractor(BaseEstimator, TransformerMixin):
    """Custom transformer for text features that pickles properly."""
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        features = []
        for text in X:
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


def load_dataset(csv_path: str):
    texts, labels = [], []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = clean_text(row.get('text', ''))
            label = row.get('category', '').strip()
            if text and label:
                texts.append(text)
                labels.append(label)
    return texts, labels


def build_pipeline(large_scale: bool = False):
    if large_scale:
        vectorizer = HashingVectorizer(
            analyzer='word',
            n_features=2 ** 18,
            alternate_sign=False,
            norm='l2',
            ngram_range=(1, 3),
            stop_words='english',
            lowercase=True,
        )
        classifier = SGDClassifier(
            loss='log_loss',
            penalty='l2',
            max_iter=5000,
            tol=1e-4,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
        return Pipeline([('vectorizer', vectorizer), ('clf', classifier)])

    # Simplified pipeline without custom transformers for reliable pickling
    word_vectorizer = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.9,
        max_features=25000,
        sublinear_tf=True,
        stop_words='english',
        strip_accents='unicode',
        lowercase=True,
    )
    return Pipeline([
        ('vectorizer', word_vectorizer),
        ('clf', LogisticRegression(
            solver='saga',
            max_iter=5000,
            class_weight='balanced',
            C=1.0,
            random_state=42,
        )),
    ])


def get_cv(labels):
    counts = Counter(labels)
    n_splits = min(5, min(counts.values()))
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)


def train(large_scale: bool = False, verbose: bool = True):
    if verbose:
        print('Loading dataset...')
    texts, labels = load_dataset(CSV_PATH)

    if verbose:
        print(f'   Loaded {len(texts)} samples across {len(set(labels))} categories')
        for label, count in sorted(Counter(labels).items()):
            print(f'   {label:12s}: {count} samples')

    pipeline = build_pipeline(large_scale=large_scale)
    cv = get_cv(labels)

    if verbose:
        print('\nRunning cross-validation...')
    scores = cross_val_score(pipeline, texts, labels, cv=cv, scoring='accuracy', n_jobs=-1)
    if verbose:
        print(f'   Accuracy: {scores.mean() * 100:.1f}% +/- {scores.std() * 100:.1f}%')

    if verbose:
        print('\nDetailed classification report:')
    predictions = cross_val_predict(pipeline, texts, labels, cv=cv, n_jobs=-1)
    if verbose:
        print(classification_report(labels, predictions, digits=3, zero_division=0))

    if verbose:
        print('\nTraining on full dataset...')
    pipeline.fit(texts, labels)
    joblib.dump(pipeline, MODEL_PATH)

    if verbose:
        print(f'\nModel saved to: {MODEL_PATH}')
        print('\nSmoke tests:')
        smoke_samples = [
            ('bought rice sugar milk grocery store', 'Groceries'),
            ('restaurant dinner biryani meal', 'Food'),
            ('uber cab ride petrol fuel', 'Travel'),
            ('doctor hospital medicine prescription', 'Medical'),
            ('school fees tuition books', 'Education'),
            ('electricity bill internet recharge', 'Other'),
        ]
        for text, expected in smoke_samples:
            try:
                probs = pipeline.predict_proba([clean_text(text)])[0]
                pred = pipeline.classes_[int(np.argmax(probs))]
                conf = float(max(probs)) * 100
            except AttributeError:
                pred = pipeline.predict([clean_text(text)])[0]
                conf = 0.0
            status = 'OK' if pred == expected else 'FAIL'
            print(f"   {status}  '{text[:40]:<40}' -> {pred} ({conf:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description='Train BillWise expense category model.')
    parser.add_argument('--large-scale', action='store_true', help='Use a HashingVectorizer + SGD classifier for large-scale training.')
    args = parser.parse_args()
    train(large_scale=args.large_scale)


if __name__ == '__main__':
    main()
