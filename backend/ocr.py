import os
import re
import shutil
import time
import cv2
import pytesseract
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from dotenv import load_dotenv
load_dotenv()

TESSERACT_PATH = os.getenv("TESSERACT_PATH")

# Common install locations, checked only as a last resort.
_FALLBACK_PATHS = [
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _resolve_tesseract_cmd():
    """
    Figure out a working tesseract binary instead of blindly trusting
    TESSERACT_PATH from .env (which is often a machine-specific,
    OS-specific path that doesn't exist on the server/deployment).
    Order of preference:
      1. TESSERACT_PATH from .env, but only if that file actually exists
      2. `tesseract` found on the system PATH (works on Linux servers
         where it's installed via apt/apk, e.g. Docker, Render, etc.)
      3. A handful of common install locations
    """
    if TESSERACT_PATH and os.path.isfile(TESSERACT_PATH):
        return TESSERACT_PATH

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    for candidate in _FALLBACK_PATHS:
        if os.path.isfile(candidate):
            return candidate

    return None


_resolved_cmd = _resolve_tesseract_cmd()

if _resolved_cmd:
    pytesseract.pytesseract.tesseract_cmd = _resolved_cmd
    print(f">>> Using tesseract binary: {_resolved_cmd}")
else:
    print(
        ">>> WARNING: Could not locate a tesseract binary. "
        "OCR will fail until Tesseract is installed and either on PATH "
        "or pointed to correctly via TESSERACT_PATH in .env."
    )



def preprocess_for_ocr(image_path: str):
    """
    Prepare a bill photo for OCR.

    Real phone photos (as opposed to clean digital scans) are large,
    noisy, unevenly lit, and often slightly blurred/skewed. Running
    adaptive thresholding on a full-resolution noisy photo turns it into
    speckle noise, which is both very slow for Tesseract to scan and
    unreadable. Normalizing to a bounded working resolution BEFORE any
    thresholding fixes both problems at once.

    Tuned for slow/shared-CPU hosting (e.g. free-tier Render): a smaller
    working resolution and a lighter blur cut CPU time substantially
    with only a small accuracy trade-off, since bill text at 1100px
    wide is still comfortably legible to Tesseract.
    """
    image = cv2.imread(image_path)

    if image is None:
        return None

    h, w = image.shape[:2]

    # Bound the working resolution. Upscale small images for legibility,
    # downscale large phone-camera photos (often 3000-4000px+) for speed.
    target_width = 1100
    if w != target_width:
        scale = target_width / w
        interpolation = cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA
        image = cv2.resize(
            image,
            (target_width, max(1, int(h * scale))),
            interpolation=interpolation
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Light Gaussian blur instead of bilateralFilter. bilateralFilter is
    # noticeably more CPU-hungry (it's an edge-preserving filter with a
    # much higher per-pixel cost) and on constrained/shared CPU hosting
    # that cost adds up to real, user-visible delay. A small Gaussian
    # blur removes sensor noise almost as effectively for this use case
    # at a fraction of the compute.
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        25,
        15
    )

    # Light morphological cleanup to remove leftover speckle noise.
    kernel = np.ones((1, 1), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    return thresh


def extract_text(image_path: str) -> str:
    print(">>> extract_text() called")
    """Extract text using Tesseract OCR."""

    if not _resolved_cmd:
        raise RuntimeError(
            "Tesseract OCR is not installed / not found. "
            "Install it and/or set TESSERACT_PATH in backend/.env to its "
            "full path (e.g. on Linux: sudo apt install tesseract-ocr; "
            "on Windows: install from https://github.com/UB-Mannheim/tesseract/wiki)."
        )

    try:
        t0 = time.time()
        processed = preprocess_for_ocr(image_path)
        t1 = time.time()
        print(f">>> preprocess_for_ocr took {t1 - t0:.2f}s")

        if processed is None:
            return ""

        pil = Image.fromarray(processed)

        text = pytesseract.image_to_string(
            pil,
            lang="eng",
            config="--oem 3 --psm 6"
        )
        t2 = time.time()
        print(f">>> tesseract image_to_string took {t2 - t1:.2f}s")
        print(f">>> TOTAL extract_text time: {t2 - t0:.2f}s")

        print("\n========== OCR OUTPUT ==========")
        print(text)
        print("================================\n")

        text = re.sub(r'\n+', '\n', text)
        print("OCR RESULT:")
        print(text)
        return text.strip()

    except Exception as e:
        print("[OCR ERROR]", e)
        return ""


def extract_shop_name(text: str) -> str:
    """Get likely shop/vendor name from first few OCR lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    skip_words = [
        'receipt', 'invoice', 'bill', 'tax', 'gst', 'total',
        'date', 'phone', 'mobile', 'address', 'cashier',
        'customer', 'consumer', 'payment', 'thank'
    ]
    skip_pattern = re.compile(
        r'\b(?:' + '|'.join(re.escape(word) for word in skip_words) + r')\b',
        re.IGNORECASE
    )

    for line in lines[:8]:
        if len(line) < 3:
            continue

        # Ignore lines which are only numbers / symbols
        if re.fullmatch(r'[\d\W]+', line):
            continue

        # Ignore lines containing normal bill labels (whole-word match only,
        # so e.g. "tax" doesn't wrongly match inside "taxi")
        if skip_pattern.search(line):
            continue

        # Ignore phone number style lines
        digits = re.sub(r'\D', '', line)
        if len(digits) >= 8:
            continue

        return line[:80]

    return "Unknown"


def extract_date(text: str) -> str:
    """Extract date from OCR text.

    Prioritizes lines that are actually labeled as a date, so a bill
    number like "CTS/24-25/1234" doesn't get mistaken for a date just
    because it contains a similar-looking digit pattern.
    """
    patterns = [
        r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b',
        r'\b(\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2})\b',
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b'
    ]

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Pass 1: lines explicitly labeled as a date (most reliable).
    # Search only the text AFTER the "date" label itself, since the same
    # line can also contain an unrelated number like a bill/invoice ID.
    for line in lines:
        label_match = re.search(r'\bdate\b\s*[:\-]?\s*', line, re.IGNORECASE)
        if not label_match:
            continue
        after_label = line[label_match.end():]
        for pattern in patterns:
            match = re.search(pattern, after_label, re.IGNORECASE)
            if match:
                return match.group(1)

    # Pass 2: any line NOT labeled as a bill/invoice/reference number,
    # to avoid picking up digits from IDs like "Bill No: CTS/24-25/1234".
    id_line_pattern = re.compile(
        r'\b(?:bill\s*no|invoice\s*no|invoice\s*#|ref(?:erence)?\s*no|order\s*no|receipt\s*no|txn\s*id|transaction\s*id)\b',
        re.IGNORECASE
    )
    for line in lines:
        if id_line_pattern.search(line):
            continue
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1)

    # Pass 3: fall back to scanning the whole text as a last resort.
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return ""


def clean_amount(value: str) -> float | None:
    """Convert OCR amount text into a valid float."""
    if not value:
        return None

    value = value.replace(',', '')
    value = value.replace('₹', '')
    value = value.replace('$', '')
    value = value.replace('Rs.', '')
    value = value.replace('Rs', '')
    value = value.replace('INR', '')
    value = value.replace('USD', '')
    value = value.strip()

    try:
        amount = float(value)

        # Reject impossible values / likely bill IDs
        if 1 <= amount <= 100000:
            return amount

    except ValueError:
        pass

    return None


def extract_currency_from_token(token: str, line: str) -> str:
    token = str(token or '').strip().lower()
    if token in ['$', 'usd']:
        return 'USD'
    if token in ['₹', 'rs.', 'rs', 'inr']:
        return 'INR'
    if 'usd' in line.lower():
        return 'USD'
    if 'inr' in line.lower() or 'rs' in line.lower() or '₹' in line:
        return 'INR'
    return 'INR'


def extract_payment_method(text: str) -> str:
    """Heuristically identify payment method from receipt text."""
    if not text:
        return "Unknown"

    normalized = text.lower()

    payment_patterns = [
        (r'\b(upi|gpay|google pay|phonepe|paytm|bhim)\b', 'UPI'),
        (r'\b(net banking|netbanking|internet banking|online banking)\b', 'Netbanking'),
        (r'\b(visa|mastercard|master card|maestro|american express|amex|debit card|credit card|card)\b', 'Card'),
        (r'\b(cash)\b', 'Cash'),
        (r'\b(wallet|paytm wallet|mobikwik|phonepe wallet|google wallet)\b', 'Wallet'),
        (r'\b(voucher|gift card|coupon)\b', 'Voucher'),
        (r'\b(emi)\b', 'EMI')
    ]

    for pattern, label in payment_patterns:
        if re.search(pattern, normalized):
            return label

    return "Unknown"


def extract_amount(text: str) -> tuple[float | None, str]:
    """
    Extract final payable amount and currency.

    Priority:
    1. Grand Total
    2. Total Amount / Total Payable / Amount Payable
    3. Net Amount / Net Total
    4. Final Total
    5. Amount near last lines only

    Important:
    Does NOT use largest number from whole receipt.
    """

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Strong labels which usually indicate final bill amount
    priority_keywords = [
        'grand total',
        'total amount payable',
        'total payable',
        'amount payable',
        'total amount',
        'net amount',
        'net total',
        'amount due',
        'balance due',
        'final total'
    ]

    # First: find a final amount on the same line or next line
    for keyword in priority_keywords:
        for index, line in enumerate(lines):
            if keyword in line.lower():

                # Search current line and one next line
                check_lines = [line]

                if index + 1 < len(lines):
                    check_lines.append(lines[index + 1])

                for check_line in check_lines:
                    matches = re.findall(
                        r'(?:(₹|rs\.?|inr|\$|usd)\s*)?([\d]{1,6}(?:,\d{3})*(?:\.\d{1,2})?)',
                        check_line,
                        re.IGNORECASE
                    )

                    if matches:
                        amount_str = matches[-1][1]
                        currency_token = matches[-1][0] or ''
                        amount = clean_amount(amount_str)

                        if amount is not None:
                            currency = extract_currency_from_token(currency_token, check_line)
                            return amount, currency

    # Second: look for lines containing only "Total"
    for index, line in enumerate(lines):
        lower_line = line.lower()

        if re.search(r'\btotal\b', lower_line):
            # Avoid subtotal and tax lines
            if any(word in lower_line for word in [
                'sub total', 'subtotal', 'tax', 'cgst', 'sgst',
                'discount', 'items', 'quantity'
            ]):
                continue

            matches = re.findall(
                r'(?:(₹|rs\.?|inr|\$|usd)\s*)?([\d]{1,6}(?:,\d{3})*(?:\.\d{1,2})?)',
                line,
                re.IGNORECASE
            )

            if matches:
                amount_str = matches[-1][1]
                currency_token = matches[-1][0] or ''
                amount = clean_amount(amount_str)

                if amount is not None:
                    currency = extract_currency_from_token(currency_token, line)
                    return amount, currency

    # Last safe fallback:
    # Check only the final 8 lines, because totals are normally at bottom.
    # Do NOT choose huge numbers like phone / invoice / consumer IDs.
    bottom_lines = lines[-8:]

    candidates = []

    for line in bottom_lines:
        # Ignore likely ID / phone / account number lines
        if re.search(
            r'(phone|mobile|invoice|bill\s*no|consumer|account|gstin|id\s*:|ticket\s*no)',
            line,
            re.IGNORECASE
        ):
            continue

        matches = re.findall(
            r'(?:(₹|rs\.?|inr|\$|usd)\s*)?([\d]{1,6}(?:,\d{3})*(?:\.\d{1,2})?)',
            line,
            re.IGNORECASE
        )

        for match in matches:
            amount_str = match[1]
            currency_token = match[0] or ''
            amount = clean_amount(amount_str)

            if amount is not None:
                currency = extract_currency_from_token(currency_token, line)
                candidates.append((amount, currency))

    # Last amount near bottom is usually final amount
    if candidates:
        return candidates[-1]

    return None, 'INR'


def scan_bill(image_path: str) -> dict:
    """Full OCR scan pipeline."""
    text = extract_text(image_path)

    shop = extract_shop_name(text)
    date = extract_date(text)
    amount, currency = extract_amount(text)
    payment_method = extract_payment_method(text)

    return {
        "extracted_text": text,
        "shop_name": shop,
        "bill_date": date,
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "amount_found": amount is not None
    }