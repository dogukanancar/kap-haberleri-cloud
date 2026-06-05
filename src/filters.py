from __future__ import annotations

import re

from src.models import Disclosure, FilterRule


def _normalize_list(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value and value.strip()]


def _disclosure_company_codes(disclosure: Disclosure) -> set[str]:
    raw = disclosure.company_code or ""
    parts = re.split(r"[,;/\s]+", raw)
    return {part.strip().lower() for part in parts if part.strip()}


def _company_matches(disclosure: Disclosure, rule_codes: list[str]) -> bool:
    if not rule_codes:
        return True
    disclosure_codes = _disclosure_company_codes(disclosure)
    if not disclosure_codes:
        return False
    return bool(disclosure_codes & set(rule_codes))


def matches_rule(disclosure: Disclosure, rule: FilterRule) -> bool:
    if not rule.aktif:
        return False

    company_codes = _normalize_list(rule.sirket_kodlari)
    if company_codes and not _company_matches(disclosure, company_codes):
        return False

    subject_oids = _normalize_list(rule.konu_oid_listesi)
    if subject_oids:
        subject_oid = (disclosure.subject_oid or "").lower()
        if subject_oid not in subject_oids:
            return False

    if rule.bildirim_sinifi:
        disclosure_class = (disclosure.disclosure_class or "").upper()
        if disclosure_class != rule.bildirim_sinifi.upper():
            return False

    searchable = " ".join(
        part
        for part in [
            disclosure.company_name or "",
            disclosure.company_code or "",
            disclosure.subject or "",
            disclosure.title or "",
            disclosure.summary or "",
        ]
        if part
    ).lower()

    exclude_words = _normalize_list(rule.haric_kelimeler)
    if exclude_words and any(word in searchable for word in exclude_words):
        return False

    include_words = _normalize_list(rule.anahtar_kelimeler)
    if include_words and not any(word in searchable for word in include_words):
        return False

    return True


def find_matching_rules(
    disclosure: Disclosure,
    rules: list[FilterRule],
) -> list[FilterRule]:
    return [rule for rule in rules if matches_rule(disclosure, rule)]


def _searchable_text(disclosure: Disclosure) -> str:
    return " ".join(
        part
        for part in [
            disclosure.company_name or "",
            disclosure.company_code or "",
            disclosure.subject or "",
            disclosure.title or "",
            disclosure.summary or "",
        ]
        if part
    ).lower()


def get_matched_keyword(disclosure: Disclosure, rule: FilterRule) -> str:
    searchable = _searchable_text(disclosure)
    for keyword in rule.anahtar_kelimeler:
        cleaned = keyword.strip()
        if cleaned and cleaned.lower() in searchable:
            return cleaned
    if rule.kural_adi.strip():
        return rule.kural_adi.strip()
    return disclosure.subject or "-"
