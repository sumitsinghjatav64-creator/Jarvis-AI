from __future__ import annotations

import hashlib
import re
from pathlib import Path
from PIL import Image, ImageStat

_PROTECTED_CHARACTERS = (
    "peppa pig", "paw patrol", "cocomelon", "jj", "baby shark", "pinkfong",
    "mickey mouse", "minnie mouse", "elsa", "anna", "frozen", "spiderman",
    "batman", "dora", "spongebob", "bluey", "bingo", "pikachu", "pokemon",
    "mario", "sonic", "chhota bheem", "motu patlu", "shinchan", "doraemon",
)

_MISLEADING_FASHION_CLAIMS = {
    "i bought this myself", "i wore this last week", "my personal closet",
    "guaranteed lowest price", "100% real human review",
}

_UNSAFE_KIDS_TERMS = {
    "violence", "weapon", "blood", "scary", "kill", "gambling", "diet pills",
    "guaranteed iq boost", "cure", "medical miracle",
}


def compute_content_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def validate_fashion_copy(script: str, caption: str, disclosure: str, is_demo: bool) -> tuple[bool, str]:
    combined = f"{script}\n{caption}".lower()
    for phrase in _MISLEADING_FASHION_CLAIMS:
        if phrase in combined:
            return False, f"Prohibited personal/misleading claim detected: '{phrase}'"
    if not disclosure or ("affiliate" not in disclosure.lower() and "demo" not in disclosure.lower()):
        return False, "Missing mandatory affiliate or demo disclosure."
    if is_demo and "#ad" in disclosure.lower() and "demo" not in disclosure.lower():
        return False, "Demo product must not be represented as a live monetized link."
    return True, "Fashion copy & disclosure verified."


def validate_kids_content(title: str, script: str, description: str) -> tuple[bool, str]:
    combined = f"{title}\n{script}\n{description}".lower()
    for char in _PROTECTED_CHARACTERS:
        if re.search(rf"\b{re.escape(char)}\b", combined):
            return False, f"Copyrighted character reference blocked: '{char}'"
    for term in _UNSAFE_KIDS_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", combined):
            return False, f"Unsuitable or misleading term for children's content: '{term}'"
    if len(script.split()) < 35:
        return False, "Script is too short or repetitive; requires beginning, middle, and end."
    return True, "Kids educational & originality checks passed."


def compare_garment_visuals(source_img_path: str, generated_img_path: str) -> tuple[float, bool]:
    """Compare dominant RGB color distribution between source product and generated model frame."""
    p1, p2 = Path(source_img_path), Path(generated_img_path)
    if not (p1.is_file() and p2.is_file()):
        return 0.0, False
    try:
        img1 = Image.open(p1).convert("RGB").resize((128, 128))
        img2 = Image.open(p2).convert("RGB").resize((128, 128))
        stat1 = ImageStat.Stat(img1).mean
        stat2 = ImageStat.Stat(img2).mean
        dist = sum(abs(a - b) for a, b in zip(stat1, stat2)) / (3.0 * 255.0)
        similarity = round(max(0.0, 1.0 - dist), 3)
        return similarity, similarity >= 0.65
    except Exception:
        return 0.0, False