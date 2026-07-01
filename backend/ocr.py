import os
import re
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from dotenv import load_dotenv

load_dotenv()

# Tesseract path from backend/.env
TESSERACT_PATH = os.getenv(
    'TESSERACT_PATH',
    r'C:\Program Files\Tesseract-OCR\tesseract.exe'
)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def preprocess_image(img: Image.Image) -> Image.Image:
    """Improve receipt image before OCR."""
    w, h = img.size

    # Increase image size for OCR
    if w < 1400:
        scale = 1400 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    img = img.convert('L')
    img = ImageEnhance.Contrast(img).enhance(2.2)
    img = img.filter(ImageFilter.SHARPEN)

    return img


def extract_text(image_path: str) -> str:
    """Extract raw text using Tesseract."""
    try:
        img = Image.open(image_path)
        img = preprocess_image(img)

        # psm 6 works well for receipt / bill layout
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        return text.strip()

    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return ""


def extract_shop_name(text: str) -> str:
    """Get likely shop/vendor name from first few OCR lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    skip_words = [
        'receipt', 'invoice', 'bill', 'tax', 'gst', 'total',
        'date', 'phone', 'mobile', 'address', 'cashier',
        'customer', 'consumer', 'payment', 'thank'
    ]

    for line in lines[:8]:
        if len(line) < 3:
            continue

        # Ignore lines which are only numbers / symbols
        if re.fullmatch(r'[\d\W]+', line):
            continue

        # Ignore lines containing normal bill labels
        if any(word in line.lower() for word in skip_words):
            continue

        # Ignore phone number style lines
        digits = re.sub(r'\D', '', line)
        if len(digits) >= 8:
            continue

        return line[:80]

    return "Unknown"


def extract_date(text: str) -> str:
    """Extract date from OCR text."""
    patterns = [
        r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b',
        r'\b(\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2})\b',
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b'
    ]

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