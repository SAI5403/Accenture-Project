import re


def check_responsibility(text: str) -> dict:
    flags = []
    score = 0

    if not text:
        return {
            "score": 0,
            "flags": [],
            "action": "Allow",
        }

    lower_text = text.lower()

    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", text):
        flags.append("Possible PII risk: email address detected")
        score += 25

    if re.search(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b", text):
        flags.append("Possible PII risk: phone number detected")
        score += 25

    if re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text):
        flags.append("Possible sensitive ID risk: Aadhaar-like number detected")
        score += 35

    risky_keywords = {
        "password": "Possible security/privacy risk: password",
        "api key": "Possible security/privacy risk: api key",
        "secret key": "Possible security/privacy risk: secret key",
        "private data": "Possible privacy risk: private data",
        "all women": "Possible bias risk: all women",
        "all men": "Possible bias risk: all men",
        "religion": "Possible bias risk: religion",
        "caste": "Possible bias risk: caste",
        "hack": "Possible harmful instruction risk: hack",
        "phishing": "Possible harmful instruction risk: phishing",
        "malware": "Possible harmful instruction risk: malware",
    }

    for keyword, message in risky_keywords.items():
        if keyword in lower_text:
            flags.append(message)
            score += 20

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
