# Verifix Template Processor

Microservice for converting filled Word documents into Verifix MERGEFIELD templates.

## What it does

1. Takes a `.docx` or `.doc` file with real data (names, dates, amounts, etc.)
2. Detects which Verifix Source (data type) best matches the document
3. Replaces **dynamic** values (employee name, salary, dates) with MERGEFIELD placeholders
4. Leaves **static** values (company name, director name) unchanged
5. Highlights unmapped values in red for manual review

## Quick Start

### Prerequisites

- Python 3.10+
- LibreOffice (for `.doc` to `.docx` conversion)

### Install

```bash
cd verifix-template-processor
pip install -r requirements.txt
```

### Run

```bash
bash run.sh
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### API Endpoints

#### Process document (returns .docx with MERGEFIELDs)

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@my_document.docx" \
  -o result_template.docx
```

#### Analyze document (returns JSON report)

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@my_document.docx" | python -m json.tool
```

#### List available sources

```bash
curl http://localhost:8000/api/v1/sources | python -m json.tool
```

#### Health check

```bash
curl http://localhost:8000/health
```

### Run Tests

```bash
pip install pytest
pytest tests/ -v
```

## Architecture

```
POST /api/v1/process
  |
  v
doc_converter.py  (.doc -> .docx via LibreOffice)
  |
  v
extractor.py      (extract text + runs from paragraphs & tables)
  |
  v
entity_recognizer.py  (regex: FIO, dates, money, INN, passport, etc.)
  |
  v
source_matcher.py     (score each Source by entity coverage)
  |
  v
mapper.py             (map entities to Source variables, filter dynamic)
  |
  v
docx_writer.py        (replace text with MERGEFIELD XML, highlight red)
  |
  v
result.docx
```

## Adding New Sources

Edit `app/sources/sources.json` and add a new entry to the `"sources"` array. No code changes required.

Each variable can have:
- `code` — technical name (used in MERGEFIELD)
- `label` — human-readable label
- `type` — `string`, `date`, `money`, `collection`
- `dynamic` — `true` = replace with MERGEFIELD, `false` = leave as-is
- `markers` — context keywords for matching
- `entity_types` — regex entity types: `FIO`, `DATE`, `MONEY`, `INN_LEGAL`, `INN_PERSON`, `PASSPORT`, `PHONE`, `DOC_NUMBER`, `JOB`, `DAYS_COUNT`, `ADDRESS`

## Known Limitations (MVP)

- No authentication
- Synchronous processing only
- No UI (API + curl only)
- Collection variables (`staffs`, `sick_leaves`) are detected but not replaced with TableStart/TableEnd MERGEFIELDs
- FIO case detection (nominative vs dative) is pattern-based, not linguistic
- Address extraction is heuristic and may miss some formats
