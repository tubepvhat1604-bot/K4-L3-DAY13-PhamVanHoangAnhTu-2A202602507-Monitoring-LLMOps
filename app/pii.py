from __future__ import annotations

import hashlib
import re

# Thứ tự quan trọng: pattern dài/cụ thể hơn chạy trước để tránh pattern ngắn
# "cắn" một phần (ví dụ thẻ 16 số không bị nhận nhầm thành số điện thoại).
# Thứ tự quan trọng: pattern cụ thể/dài chạy trước để pattern ngắn không "cắn" một
# phần (ví dụ thẻ 16 số không bị nhận nhầm thành số điện thoại).
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    # Thẻ thanh toán 16 số, ngăn cách bằng dấu cách hoặc gạch ngang.
    "credit_card": r"(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)",
    # CCCD Việt Nam: đúng 12 chữ số.
    "cccd": r"(?<!\d)\d{12}(?!\d)",
    # Số điện thoại VN: +84 hoặc 0 + 9 chữ số, ngăn cách " ", "." hoặc "-".
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # Hộ chiếu VN: 1 chữ cái in hoa + 7 chữ số (ví dụ B1234567).
    "passport": r"\b[A-Z]\d{7}\b",
    # Địa chỉ: "12 đường Lê Lợi", "45 ngõ ...", cắt tới dấu phẩy/chấm.
    "address_vn": r"(?i)\b\d{1,4}[a-z]?(?:/\d+)?\s+(?:đường|phố|ngõ|ngách|hẻm)\s+[^,.;\n]{1,40}",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
