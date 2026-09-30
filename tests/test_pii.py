from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD của tôi là 012345678901")
    assert "012345678901" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_formats() -> None:
    for card in ("4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"):
        out = scrub_text(f"Card {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_card_is_not_mislabeled_as_phone() -> None:
    out = scrub_text("Card 0123 4567 8901 2345")
    assert "REDACTED_CREDIT_CARD" in out
    assert "PHONE" not in out


def test_scrub_passport_and_address() -> None:
    out = scrub_text("Passport B1234567, ở 12 đường Lê Lợi, Hà Nội")
    assert "B1234567" not in out
    assert "REDACTED_PASSPORT" in out
    assert "Lê Lợi" not in out


def test_scrub_leaves_clean_text_untouched() -> None:
    text = "Explain monitoring and traces"
    assert scrub_text(text) == text
