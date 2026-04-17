from __future__ import annotations
import regex
from app.models import Entity
from app.config import CONTEXT_WINDOW

# ──────────────────────────────────────────────────────
# Stop-words: multi-word phrases that look like FIO but are not
# ──────────────────────────────────────────────────────
_FIO_STOP_PHRASES = {
    # Document titles / headings
    "трудовой договор", "трудового договора", "трудовому договору",
    "коллективный договор", "коллективного договора",
    "отдел маркетинга", "отдел кадров", "отдел продаж",
    "отдел контроля", "отдел контроля качества",
    "генеральный директор", "генерального директора",
    "заработная плата", "заработной платы", "заработную плату",
    "больничный лист", "больничного листа",
    "командировочное удостоверение",
    "табельный номер",
    "российская федерация", "республика узбекистан",
    "трудовой кодекс", "трудового кодекса",
    "настоящий договор", "настоящего договора", "настоящему договору",
    "испытательный срок", "испытательного срока",
    "рабочее время", "рабочего времени",
    "должностная инструкция", "должностной инструкции",
    "производственная необходимость", "производственной необходимости",
    "календарных дней", "рабочих дней",
    "место назначения",
    "социальный налог", "социального налога",
    "материальная ответственность", "материальной ответственности",
}

# Single stop-words that should not be part of FIO matches
_FIO_STOP_WORDS = {
    "приказ", "договор", "соглашение", "заявление", "справка",
    "протокол", "акт", "ведомость", "журнал", "реестр",
    "утверждаю", "приложение", "основание", "примечание",
}

# Words that can start a phrase looking like FIO but are actually titles/roles
_FIO_PREFIX_STOPS = {
    "начальник", "директор", "генеральный", "заместитель",
    "главный", "старший", "ведущий", "младший",
    "отдел", "департамент", "управление", "служба",
    "производственная", "командировочное", "настоящий",
    "материальная", "должностная", "испытательный",
    "рабочее", "социальный", "календарных", "рабочих",
    # Common verbs that precede FIO in documents
    "направить", "назначить", "перевести", "уволить",
    "принять", "допустить", "командировать", "откомандировать",
    "премировать", "наградить", "объявить",
}

# ──────────────────────────────────────────────────────
# Job title dictionary (common positions)
# ──────────────────────────────────────────────────────
_JOB_TITLES = [
    "директор", "генеральный директор", "заместитель директора",
    "главный бухгалтер", "бухгалтер", "старший бухгалтер",
    "менеджер", "продакт-менеджер", "проект-менеджер",
    "инженер", "старший инженер", "программист",
    "контролёр", "контролер", "оператор", "техник",
    "специалист", "ведущий специалист", "главный специалист",
    "начальник", "начальник отдела", "руководитель",
    "секретарь", "делопроизводитель", "кадровик",
    "экономист", "аналитик", "юрист", "юрисконсульт",
    "водитель", "охранник", "уборщик", "грузчик",
    "продавец", "кассир", "торговый представитель",
    "врач", "медсестра", "фармацевт", "провизор",
    "лаборант", "химик", "технолог",
    "дизайнер", "маркетолог", "копирайтер",
    "логист", "кладовщик", "снабженец",
    "слесарь", "электрик", "сварщик", "токарь", "фрезеровщик",
    "монтажник", "наладчик", "механик",
]

# Month names for date parsing
_MONTHS_RU = {
    "января": "01", "февраля": "02", "марта": "03", "апреля": "04",
    "мая": "05", "июня": "06", "июля": "07", "августа": "08",
    "сентября": "09", "октября": "10", "ноября": "11", "декабря": "12",
    "январь": "01", "февраль": "02", "март": "03", "апрель": "04",
    "май": "05", "июнь": "06", "июль": "07", "август": "08",
    "сентябрь": "09", "октябрь": "10", "ноябрь": "11", "декабрь": "12",
}


def _get_context(text: str, start: int, end: int, window: int = CONTEXT_WINDOW) -> str:
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    return text[ctx_start:ctx_end]


def _is_fio_stop(candidate: str) -> bool:
    lower = candidate.lower().strip()
    if lower in _FIO_STOP_PHRASES:
        return True
    words = lower.split()
    if len(words) == 1 and words[0] in _FIO_STOP_WORDS:
        return True
    # Filter out single-word matches that are common nouns
    if len(words) == 1:
        return True  # Real FIO has at least 2 words (Surname Name)
    # If first word is a title/role prefix, not a name
    if words and words[0] in _FIO_PREFIX_STOPS:
        return True
    # If any word is in stop phrases list (partial match)
    for phrase in _FIO_STOP_PHRASES:
        if lower.startswith(phrase) or lower.endswith(phrase):
            return True
    return False


def recognize_entities(text: str) -> list[Entity]:
    """Runs all regex extractors and returns a deduplicated list of entities."""
    entities: list[Entity] = []

    # Short FIO first (higher priority — "Иванов И.И." should not be split)
    entities.extend(_extract_fio_short_ru(text))
    entities.extend(_extract_fio_full_ru(text))
    entities.extend(_extract_fio_latin(text))
    entities.extend(_extract_dates(text))
    entities.extend(_extract_money(text))
    entities.extend(_extract_inn(text))
    entities.extend(_extract_passport(text))
    entities.extend(_extract_phone(text))
    entities.extend(_extract_doc_number(text))
    entities.extend(_extract_days_count(text))
    entities.extend(_extract_address(text))

    # Deduplicate overlapping entities (keep longer match)
    entities = _deduplicate(entities)
    return entities


# ──────────────────────────────────────────────
# FIO — Russian full (Фамилия Имя Отчество)
# ──────────────────────────────────────────────
def _extract_fio_full_ru(text: str) -> list[Entity]:
    results = []
    # Try 3-word FIO first, then 2-word
    pattern_3w = r'[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}'
    pattern_2w = r'[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}'

    # First pass: 3-word FIO (most specific)
    for m in regex.finditer(pattern_3w, text):
        candidate = m.group().strip()
        words = candidate.split()

        # If first word is a stop prefix, try re-matching from word[1] position
        if words[0].lower() in _FIO_PREFIX_STOPS:
            # Look for 3-word FIO starting after the stop word
            rest_start = m.start() + len(words[0]) + 1
            rest_match = regex.match(pattern_3w, text[rest_start:])
            if rest_match:
                fio_text = rest_match.group().strip()
                if not _is_fio_stop(fio_text):
                    results.append(Entity(
                        text=fio_text, type="FIO",
                        start=rest_start, end=rest_start + rest_match.end(),
                        context=_get_context(text, rest_start, rest_start + rest_match.end()),
                    ))
                    continue
            # Fall through to 2-word match below
            continue

        if _is_fio_stop(candidate):
            continue
        if all(2 <= len(w) <= 25 for w in words):
            results.append(Entity(
                text=candidate, type="FIO",
                start=m.start(), end=m.end(),
                context=_get_context(text, m.start(), m.end()),
            ))

    # Second pass: 2-word FIO (only where not already covered)
    for m in regex.finditer(pattern_2w, text):
        candidate = m.group().strip()
        words = candidate.split()

        if words[0].lower() in _FIO_PREFIX_STOPS:
            continue
        if _is_fio_stop(candidate):
            continue
        if len(words) < 2:
            continue

        # Check not overlapping with existing
        overlaps = any(
            m.start() < e.end and m.end() > e.start
            for e in results
        )
        if not overlaps and all(2 <= len(w) <= 25 for w in words):
            results.append(Entity(
                text=candidate, type="FIO",
                start=m.start(), end=m.end(),
                context=_get_context(text, m.start(), m.end()),
            ))

    return results


# ──────────────────────────────────────────────
# FIO — Russian short (Иванов И.И.)
# ──────────────────────────────────────────────
def _extract_fio_short_ru(text: str) -> list[Entity]:
    results = []
    pattern = r'[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.'
    for m in regex.finditer(pattern, text):
        candidate = m.group().strip()
        if _is_fio_stop(candidate):
            continue
        results.append(Entity(
            text=candidate,
            type="FIO",
            start=m.start(),
            end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    return results


# ──────────────────────────────────────────────
# FIO — Uzbek/Latin (Karimov Sherzod)
# ──────────────────────────────────────────────
def _extract_fio_latin(text: str) -> list[Entity]:
    results = []
    pattern = r"[A-Z][a-z]{1,25}(?:ov|ova|ev|eva|yev|yeva)\s+[A-Z][a-z]{1,25}(?:\s+[A-Z][a-z]{1,25})?"
    for m in regex.finditer(pattern, text):
        candidate = m.group().strip()
        results.append(Entity(
            text=candidate,
            type="FIO",
            start=m.start(),
            end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    return results


# ──────────────────────────────────────────────
# Dates
# ──────────────────────────────────────────────
def _extract_dates(text: str) -> list[Entity]:
    results = []

    # dd.mm.yyyy or dd/mm/yyyy or dd-mm-yyyy
    for m in regex.finditer(r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', text):
        results.append(Entity(
            text=m.group(), type="DATE",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))

    # «dd» month yyyy or "dd" month yyyy
    for m in regex.finditer(r'[«"]\s*\d{1,2}\s*[»"]\s+[а-яё]+\s+\d{4}', text):
        results.append(Entity(
            text=m.group(), type="DATE",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))

    # dd month yyyy (without quotes) e.g. "13 июня 2023"
    months_pattern = '|'.join(_MONTHS_RU.keys())
    for m in regex.finditer(rf'\d{{1,2}}\s+(?:{months_pattern})\s+\d{{4}}', text, flags=regex.IGNORECASE):
        results.append(Entity(
            text=m.group(), type="DATE",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))

    # Uzbek date: yyyy-yil dd-month or yyyy yil
    for m in regex.finditer(r'\d{4}[\s-]?yil\s+\d{1,2}[\s-]?\w+', text, flags=regex.IGNORECASE):
        results.append(Entity(
            text=m.group(), type="DATE",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))

    return results


# ──────────────────────────────────────────────
# Money / Sums
# ──────────────────────────────────────────────
def _extract_money(text: str) -> list[Entity]:
    results = []
    # Number (with optional space-separated thousands) + currency
    pattern = r"[\d][\d\s.,]*\s*(?:сум|so['\u2019]m|UZS|USD|\$|евро|руб)"
    for m in regex.finditer(pattern, text, flags=regex.IGNORECASE):
        candidate = m.group().strip()
        # Must contain at least one digit
        if regex.search(r'\d', candidate):
            results.append(Entity(
                text=candidate, type="MONEY",
                start=m.start(), end=m.end(),
                context=_get_context(text, m.start(), m.end()),
            ))
    return results


# ──────────────────────────────────────────────
# INN (Tax ID)
# ──────────────────────────────────────────────
def _extract_inn(text: str) -> list[Entity]:
    results = []
    # 14-digit INN (individual) — must check first (longer match)
    for m in regex.finditer(r'(?<!\d)\d{14}(?!\d)', text):
        results.append(Entity(
            text=m.group(), type="INN_PERSON",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    # 9-digit INN (legal entity) — exclude if part of longer number
    for m in regex.finditer(r'(?<!\d)\d{9}(?!\d)', text):
        # Check not already captured as part of 14-digit
        overlap = False
        for existing in results:
            if existing.start <= m.start() and existing.end >= m.end():
                overlap = True
                break
        if not overlap:
            # Check context for INN-related keywords
            ctx = _get_context(text, m.start(), m.end()).lower()
            if any(kw in ctx for kw in ['инн', 'inn', 'стир', 'stir', 'идентификац']):
                results.append(Entity(
                    text=m.group(), type="INN_LEGAL",
                    start=m.start(), end=m.end(),
                    context=_get_context(text, m.start(), m.end()),
                ))
    return results


# ──────────────────────────────────────────────
# Passport
# ──────────────────────────────────────────────
def _extract_passport(text: str) -> list[Entity]:
    results = []
    # Uzbek passport: 2 letters + optional № + 7 digits
    pattern = r'[A-ZА-ЯЁ]{2}\s*№?\s*\d{7}'
    for m in regex.finditer(pattern, text):
        results.append(Entity(
            text=m.group().strip(), type="PASSPORT",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    return results


# ──────────────────────────────────────────────
# Phone
# ──────────────────────────────────────────────
def _extract_phone(text: str) -> list[Entity]:
    results = []
    pattern = r'\+?998[\s\-\(]*\d{2}[\)\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}'
    for m in regex.finditer(pattern, text):
        results.append(Entity(
            text=m.group().strip(), type="PHONE",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    return results


# ──────────────────────────────────────────────
# Document number
# ──────────────────────────────────────────────
def _extract_doc_number(text: str) -> list[Entity]:
    results = []
    pattern = r'№\s*[\w\d/\-]+'
    for m in regex.finditer(pattern, text):
        candidate = m.group().strip()
        if len(candidate) > 2:  # more than just "№"
            results.append(Entity(
                text=candidate, type="DOC_NUMBER",
                start=m.start(), end=m.end(),
                context=_get_context(text, m.start(), m.end()),
            ))
    return results


# ──────────────────────────────────────────────
# Days count
# ──────────────────────────────────────────────
def _extract_days_count(text: str) -> list[Entity]:
    results = []
    pattern = r'\d{1,3}\s*(?:календарных\s+дней|рабочих\s+дней|дней|kun)'
    for m in regex.finditer(pattern, text, flags=regex.IGNORECASE):
        results.append(Entity(
            text=m.group().strip(), type="DAYS_COUNT",
            start=m.start(), end=m.end(),
            context=_get_context(text, m.start(), m.end()),
        ))
    return results


# ──────────────────────────────────────────────
# Address (heuristic — trigger words)
# ──────────────────────────────────────────────
def _extract_address(text: str) -> list[Entity]:
    results = []
    # Look for address patterns with trigger words
    triggers = [
        r'(?:г\.|город)\s*[А-ЯЁа-яё\w]+(?:,\s*[^\n,]{3,50}){1,4}',
        r'(?:ул\.|улица)\s*[А-ЯЁа-яё\w]+(?:,\s*[^\n,]{3,30}){0,3}',
        r'\d{6},?\s*[А-ЯЁ][а-яё]+(?:,\s*[^\n,]{3,50}){1,4}',  # postal code
    ]
    for trigger in triggers:
        for m in regex.finditer(trigger, text):
            candidate = m.group().strip()
            if len(candidate) > 10:
                results.append(Entity(
                    text=candidate, type="ADDRESS",
                    start=m.start(), end=m.end(),
                    context=_get_context(text, m.start(), m.end()),
                ))
    return results


# ──────────────────────────────────────────────
# Deduplication
# ──────────────────────────────────────────────
def _deduplicate(entities: list[Entity]) -> list[Entity]:
    """Remove overlapping entities, keeping the longer/more specific one."""
    if not entities:
        return entities

    # Sort by start position, then by length descending
    entities.sort(key=lambda e: (e.start, -(e.end - e.start)))

    result: list[Entity] = []
    for entity in entities:
        # Check if this entity overlaps with any already accepted
        overlaps = False
        for accepted in result:
            if entity.start < accepted.end and entity.end > accepted.start:
                overlaps = True
                break
        if not overlaps:
            result.append(entity)

    return result
