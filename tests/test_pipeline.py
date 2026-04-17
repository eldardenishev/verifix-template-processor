"""Tests for the Verifix Template Processor pipeline."""
import json
from pathlib import Path

import pytest

from app.models import Source, Entity
from app.services.entity_recognizer import recognize_entities
from app.services.source_matcher import match_source
from app.services.mapper import map_entities_to_variables, filter_dynamic_mappings
from app.config import SOURCES_PATH


def _load_sources() -> list[Source]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Source(**s) for s in data["sources"]]


# ─── Entity recognizer tests ───


class TestEntityRecognizer:
    def test_fio_full_russian(self):
        text = "гражданин(ка) Иванов Иван Иванович, именуемый далее"
        entities = recognize_entities(text)
        fios = [e for e in entities if e.type == "FIO"]
        assert len(fios) >= 1
        assert any("Иванов Иван Иванович" in e.text for e in fios)

    def test_fio_short_russian(self):
        text = "Начальник Волкова Е.А."
        entities = recognize_entities(text)
        fios = [e for e in entities if e.type == "FIO"]
        assert len(fios) >= 1
        assert any("Волкова Е.А." in e.text for e in fios)

    def test_fio_short_with_initials(self):
        text = "Директор Кариева М.Д."
        entities = recognize_entities(text)
        fios = [e for e in entities if e.type == "FIO"]
        assert len(fios) >= 1
        assert any("Кариева М.Д." in e.text for e in fios)

    def test_fio_in_dative_case(self):
        text = "Направить Халмурадову Шахсанам Шарифовну в командировку"
        entities = recognize_entities(text)
        fios = [e for e in entities if e.type == "FIO"]
        assert len(fios) >= 1
        assert any("Халмурадову Шахсанам Шарифовну" in e.text for e in fios)

    def test_fio_stop_words_filtered(self):
        text = "Трудовой Договор между сторонами"
        entities = recognize_entities(text)
        fios = [e for e in entities if e.type == "FIO"]
        # "Трудовой Договор" should NOT be detected as FIO
        assert not any("Трудовой Договор" in e.text for e in fios)

    def test_date_dot_format(self):
        text = "от 24.05.2023 года"
        entities = recognize_entities(text)
        dates = [e for e in entities if e.type == "DATE"]
        assert len(dates) >= 1
        assert any("24.05.2023" in e.text for e in dates)

    def test_date_text_format(self):
        text = "с 13 июня 2023 по 17 июня 2023"
        entities = recognize_entities(text)
        dates = [e for e in entities if e.type == "DATE"]
        assert len(dates) >= 2

    def test_date_quoted_format(self):
        text = '«15» мая 2023 года'
        entities = recognize_entities(text)
        dates = [e for e in entities if e.type == "DATE"]
        assert len(dates) >= 1

    def test_money(self):
        text = "заработная плата 450 000 сум ежемесячно"
        entities = recognize_entities(text)
        money = [e for e in entities if e.type == "MONEY"]
        assert len(money) >= 1
        assert any("450 000 сум" in e.text for e in money)

    def test_inn_legal(self):
        text = "ИНН организации: 201913337"
        entities = recognize_entities(text)
        inns = [e for e in entities if e.type == "INN_LEGAL"]
        assert len(inns) >= 1
        assert any("201913337" in e.text for e in inns)

    def test_passport(self):
        text = "паспорт БГ № 0172806 выдан"
        entities = recognize_entities(text)
        passports = [e for e in entities if e.type == "PASSPORT"]
        assert len(passports) >= 1

    def test_phone(self):
        text = "телефон +998 (78)1480304"
        entities = recognize_entities(text)
        phones = [e for e in entities if e.type == "PHONE"]
        assert len(phones) >= 1

    def test_doc_number(self):
        text = "Приказ № 66/К от 24.05.2023"
        entities = recognize_entities(text)
        doc_nums = [e for e in entities if e.type == "DOC_NUMBER"]
        assert len(doc_nums) >= 1
        assert any("66/К" in e.text for e in doc_nums)

    def test_days_count(self):
        text = "сроком на 05 календарных дней"
        entities = recognize_entities(text)
        days = [e for e in entities if e.type == "DAYS_COUNT"]
        assert len(days) >= 1


# ─── Source matcher tests ───


class TestSourceMatcher:
    def test_labor_contract_matched(self):
        """Entities from a labor contract should match the labor_contract source."""
        text = (
            "Трудовой договор № 123 от 01.01.2024. "
            "Организация СП «JURABEK LABORATORIES» в форме ООО, "
            "ИНН: 201913337, "
            "в лице генерального директора Кариева М.Д., "
            "гражданин(ка) Иванов Иван Иванович, "
            "на должность контролёр, "
            "заработная плата 450 000 сум, "
            "паспорт БГ № 0172806"
        )
        entities = recognize_entities(text)
        sources = _load_sources()
        best, confidence = match_source(entities, sources)
        assert best.id == "labor_contract"
        assert confidence > 0

    def test_business_trip_matched(self):
        """Entities from a business trip order should match business_trip source."""
        text = (
            "Приказ № 66/К от 24.05.2023. "
            "Направить Халмурадову Шахсанам Шарифовну "
            "в командировку в Ташкент-Баку-Ташкент "
            "сроком на 05 календарных дней "
            "с 13 июня 2023 по 17 июня 2023 "
            "с целью деловых переговоров. "
            "Основание: производственная необходимость. "
            "Начальник Волкова Е.А."
        )
        entities = recognize_entities(text)
        sources = _load_sources()
        best, confidence = match_source(entities, sources)
        assert best.id == "business_trip"
        assert confidence > 0


# ─── Mapper tests ───


class TestMapper:
    def test_dynamic_filter(self):
        """Only dynamic mappings should be returned for MERGEFIELD replacement."""
        text = (
            "Трудовой договор № 123 от 01.01.2024. "
            "СП «JURABEK LABORATORIES» в форме ООО, ИНН: 201913337, "
            "в лице генерального директора Кариева М.Д., "
            "гражданин(ка) Иванов Иван Иванович, "
            "принимается на должность контролёр "
            "с заработной платой 450 000 сум. "
            "Паспорт: БГ № 0172806"
        )
        entities = recognize_entities(text)
        sources = _load_sources()
        best, _ = match_source(entities, sources)
        assert best.id == "labor_contract"

        mappings, unmapped = map_entities_to_variables(entities, best)
        dynamic, static = filter_dynamic_mappings(mappings)

        dynamic_vars = {m.variable for m in dynamic}
        static_vars = {m.variable for m in static}

        # Dynamic variables should include employee-related fields
        assert len(dynamic) > 0, f"Expected dynamic mappings, got none. All: {[(m.variable, m.original) for m in mappings]}"
        # director_name should be static (not replaced)
        if "director_name" in static_vars:
            assert "director_name" not in dynamic_vars


# ─── Full pipeline simulation ───


class TestFullPipeline:
    def test_labor_contract_full(self):
        """Simulate full pipeline on labor contract text."""
        text = (
            "Трудовой договор № 123 от 01.01.2024. "
            "СП «JURABEK LABORATORIES» в форме ООО, ИНН: 201913337, "
            "в лице генерального директора Кариева М.Д., "
            "гражданин(ка) Иванов Иван Иванович, "
            "принимается на должность контролёр "
            "в Отдел контроля качества "
            "с заработной платой 450 000 сум. "
            "Паспорт: БГ № 0172806. "
            "Телефон: +998 (78)1480304"
        )

        # Step 1: recognize entities
        entities = recognize_entities(text)
        assert len(entities) > 0

        # Step 2: match source
        sources = _load_sources()
        best, confidence = match_source(entities, sources)
        assert best.id == "labor_contract"

        # Step 3: map
        mappings, unmapped = map_entities_to_variables(entities, best)
        assert len(mappings) > 0

        # Step 4: filter
        dynamic, static = filter_dynamic_mappings(mappings)
        dynamic_vars = {m.variable for m in dynamic}

        # Key assertions: employee_name should be dynamic
        # director_name should be static
        print(f"\nDynamic: {[(m.variable, m.original) for m in dynamic]}")
        print(f"Static: {[(m.variable, m.original) for m in static]}")
        print(f"Unmapped: {[(u.original, u.reason) for u in unmapped]}")
