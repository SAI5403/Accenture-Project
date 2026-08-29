import re


def check_responsibility(text: str) -> dict:
    flags = []
    score = 0

    lower_text = text.lower()

    email_pattern = r"\b[\w\.-]+@[\w\.-]+\.\w+\b"
    phone_pattern = r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"
    credit_card_pattern = r"\b(?:\d[ -]*?){13,16}\b"
    aadhaar_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"

    if re.search(email_pattern, text):
        flags.append("Possible PII risk: email address detected")
        score += 25

    if re.search(phone_pattern, text):
        flags.append("Possible PII risk: phone number detected")
        score += 25

    if re.search(credit_card_pattern, text):
        flags.append("Possible financial data risk: credit card-like number detected")
        score += 35

    if re.search(aadhaar_pattern, text):
        flags.append("Possible sensitive ID risk: Aadhaar-like number detected")
        score += 35

    unsafe_keywords = [
        "password",
        "api key",
        "secret key",
        "private key",
        "confidential",
        "internal only",
    ]

    bias_keywords = [
        "all women",
        "all men",
        "all muslims",
        "all hindus",
        "all christians",
        "lower caste",
        "upper caste",
        "race",
        "religion",
    ]

    harmful_keywords = [
        "hack",
        "bypass security",
        "steal",
        "phishing",
        "malware",
        "exploit",
    ]

    for word in unsafe_keywords:
        if word in lower_text:
            flags.append(f"Possible security/privacy risk: {word}")
            score += 20

    for word in bias_keywords:
        if word in lower_text:
            flags.append(f"Possible bias risk: {word}")
            score += 20

    for word in harmful_keywords:
        if word in lower_text:
            flags.append(f"Possible harmful instruction risk: {word}")
            score += 25

    score = min(score, 100)

    if score >= 75:
        action = "Human Review"
    elif score >= 50:
        action = "Rewrite / Verify"
    elif score >= 20:
        action = "Allow + Monitor"
    else:
        action = "Allow"

    return {
        "score": score,
        "flags": flags,
        "action": action,
    }
