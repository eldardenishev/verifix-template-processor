from __future__ import annotations
from pydantic import BaseModel


class VariableField(BaseModel):
    code: str
    label: str
    type: str = "string"
    dynamic: bool = True
    markers: list[str] = []
    entity_types: list[str] = []


class Variable(BaseModel):
    code: str
    label: str
    type: str = "string"
    dynamic: bool = True
    markers: list[str] = []
    entity_types: list[str] = []
    fields: list[VariableField] = []  # for collections


class Source(BaseModel):
    id: str
    name: str
    description: str = ""
    variables: list[Variable] = []


class Entity(BaseModel):
    text: str
    type: str  # FIO, DATE, MONEY, INN_LEGAL, INN_PERSON, PASSPORT, PHONE, ADDRESS, DOC_NUMBER, JOB, DAYS_COUNT
    start: int  # position in full text
    end: int
    context: str = ""  # surrounding text +-50 chars
    paragraph_index: int = -1
    source_location: str = "paragraph"  # "paragraph" or "table"


class MappingEntry(BaseModel):
    original: str
    variable: str
    variable_label: str = ""
    context: str = ""
    dynamic: bool = True
    confidence: float = 0.0


class UnmappedEntry(BaseModel):
    original: str
    entity_type: str = ""
    reason: str = ""
    context: str = ""


class AnalysisResult(BaseModel):
    detected_source: str
    detected_source_id: str = ""
    confidence: float
    mappings: list[MappingEntry] = []
    unmapped: list[UnmappedEntry] = []


class RunInfo(BaseModel):
    text: str
    bold: bool | None = None
    italic: bool | None = None
    font_name: str | None = None
    font_size: float | None = None
    start: int = 0
    end: int = 0
