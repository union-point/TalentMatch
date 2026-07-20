import logging
import math
import re
import unicodedata

from app.domain.value_objects import InjectionScanResult

logger = logging.getLogger(__name__)

INJECTION_PHRASE_LIBRARY: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?(previous|prior|instructions?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+are", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+are", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"###\s*(system|human|assistant)\s*:", re.IGNORECASE),
    re.compile(r"human:", re.IGNORECASE),
    re.compile(r"assistant:", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"output\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"print\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(restrictions|safeguards|guardrails)", re.IGNORECASE),
    re.compile(r"remove\s+(all\s+)?(restrictions|constraints|limitations)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(not\s+)?(bound|restricted)\s+by", re.IGNORECASE),
    re.compile(r"do\s+(not\s+)?(follow|obey)\s+(your\s+)?(instructions|guidelines)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"dan\s*:", re.IGNORECASE),
]


SUSPICIOUS_UNICODE_CATEGORIES = frozenset(
    {
        "Cf",
        "Cc",
        "Mn",
        "Zl",
        "Zp",
    }
)


def _scan_invisible_characters(text: str) -> list[str]:
    findings: list[str] = []
    seen_categories: set[str] = set()
    for char in text:
        category = unicodedata.category(char)
        if category in SUSPICIOUS_UNICODE_CATEGORIES and char not in ("\n", "\t", "\r"):
            if category not in seen_categories:
                cat_name = unicodedata.category(char)
                char_name = unicodedata.name(char, "unknown")
                findings.append(f"Invisible character category {cat_name} ({char_name})")
                seen_categories.add(category)
    return findings


def _find_known_injection_phrases(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in INJECTION_PHRASE_LIBRARY:
        if pattern.search(text):
            findings.append(f"Known injection phrase matched: {pattern.pattern[:60]}")
    return findings


def _scan_hidden_content(text: str) -> list[str]:
    findings: list[str] = []
    hidden_patterns = [
        (re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL), "HTML script tag"),
        (re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL), "HTML style tag"),
        (re.compile(r"<!--.*?-->", re.DOTALL), "HTML comment"),
        (re.compile(r"display\s*:\s*none", re.IGNORECASE), "CSS display:none"),
        (re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE), "CSS visibility:hidden"),
        (re.compile(r"font-size\s*:\s*0", re.IGNORECASE), "CSS font-size:0"),
        (re.compile(r"color\s*:\s*#?fff(fff)?", re.IGNORECASE), "CSS color:white"),
        (re.compile(r"color\s*:\s*white", re.IGNORECASE), "CSS color:white"),
        (re.compile(r"opacity\s*:\s*0", re.IGNORECASE), "CSS opacity:0"),
        (
            re.compile(r"position\s*:\s*absolute;\s*(left|top)\s*:\s*-\d+", re.IGNORECASE),
            "CSS off-screen positioning",
        ),
        (re.compile(r"z-index\s*:\s*-\d+", re.IGNORECASE), "CSS negative z-index"),
    ]
    for pattern, label in hidden_patterns:
        if pattern.search(text):
            findings.append(f"Hidden content pattern: {label}")
    return findings


def _compute_entropy(text: str) -> float:
    if not text:
        return 0.0
    text_len = len(text)
    freq: dict[str, int] = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    entropy = 0.0
    for count in freq.values():
        p = count / text_len
        entropy -= p * math.log2(p)
    return entropy


MIN_ENTROPY_THRESHOLD = 6.0
"""Entropy above this value is flagged as anomalous (possible encoded/obfuscated payload)."""

PASS_THRESHOLD = 15
"""Scores at or above this threshold cause the scan to fail."""


def detect_injection(text: str) -> InjectionScanResult:
    findings: dict[str, object] = {}
    score = 0

    invisible = _scan_invisible_characters(text)
    if invisible:
        findings["invisible_characters"] = invisible
        score += 30

    phrases = _find_known_injection_phrases(text)
    if phrases:
        findings["known_injection_phrases"] = phrases
        score += min(len(phrases) * 15, 40)

    hidden = _scan_hidden_content(text)
    if hidden:
        findings["hidden_content"] = hidden
        score += 25

    entropy = _compute_entropy(text)
    if len(text) > 100 and entropy > MIN_ENTROPY_THRESHOLD:
        findings["high_entropy"] = (
            f"Text entropy {entropy:.2f} exceeds threshold {MIN_ENTROPY_THRESHOLD}"
        )
        score += 15

    score = min(score, 100)
    passed = score < PASS_THRESHOLD

    if not passed:
        logger.warning(
            "Prompt injection detected (score=%d): %s",
            score,
            findings,
        )

    return InjectionScanResult(
        passed=passed,
        suspicion_score=score,
        details=findings if findings else None,
    )
