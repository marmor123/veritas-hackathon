"""
Shared Pydantic schemas for the VERITAS pipeline.
All modules agree on these types.
"""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class Severity(str, Enum):
    WARNING = "WARNING"      # Needs urgent medical attention
    CAUTION = "CAUTION"      # Needs follow-up within weeks
    ADVISORY = "ADVISORY"    # Lifestyle/awareness


class Confidence(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class BiomarkerResult(BaseModel):
    name: str                 # e.g., "Ferritin"
    value: float              # e.g., 12.0
    unit: str                 # e.g., "ng/mL"
    ref_low: Optional[float] = None  # e.g., 15.0
    ref_high: Optional[float] = None  # e.g., 150.0
    flag: Optional[str] = None       # "H"/"L"/"high"/"low"/"normal" or None


class Medication(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None


class WearableData(BaseModel):
    resting_hr_avg: Optional[float] = None
    resting_hr_trend: Optional[str] = None   # "rising", "falling", "stable"
    hrv_avg: Optional[float] = None
    hrv_trend: Optional[str] = None
    sleep_avg_hours: Optional[float] = None
    sleep_quality: Optional[str] = None      # "good", "fair", "poor"
    activity_avg_steps: Optional[float] = None
    daily_data: Optional[List[dict]] = None  # [{date, hr, hrv, sleep, steps}, ...]


class QualityFlag(BaseModel):
    type: str                 # "hemolysis", "plausibility", "consistency"
    severity: str             # "high", "medium", "low"
    detail: str               # Human-readable explanation
    affected_biomarkers: List[str]


class DrugInterference(BaseModel):
    biomarker: str
    drug: str
    effect: str               # e.g., "falsely elevates"
    recommendation: str       # e.g., "Stop biotin 72h before retest"


class VerifiedResult(BaseModel):
    biomarker: str
    value: float
    unit: str
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flagged: bool
    flag_reason: Optional[str] = None


class VerificationOutput(BaseModel):
    verified_results: List[VerifiedResult]
    drug_interferences: List[DrugInterference]
    corrected_values: List[dict]    # [{name, raw_value, corrected_value, formula}]
    quality_flags: List[QualityFlag]


class RetrievedChunk(BaseModel):
    chunk_id: str
    source: str               # e.g., "Wallach Ch.3"
    text: str
    relevance_score: float
    biomarkers_involved: List[str]


class RAGOutput(BaseModel):
    matched_patterns: List[dict]    # [{pattern_name, confidence, supporting_biomarkers,
                                    #   retrieved_chunks, differential}]
    unmatched_abnormal_biomarkers: List[str]


class GraphNode(BaseModel):
    """A node in the clinical knowledge graph."""
    id: str
    label: str
    type: str                 # "biomarker", "pattern", "system", "symptom"
    severity: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None


class GraphEdge(BaseModel):
    """An edge in the clinical knowledge graph."""
    source: str               # node id
    target: str               # node id
    relation: str             # "supports", "causes", "may_cause", "belongs_to", "contributes_to"
    weight: Optional[float] = None


class ClinicalGraph(BaseModel):
    """Knowledge graph representing biomarker relationships."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class PatternResult(BaseModel):
    name: str                  # Patient-friendly name
    severity: Severity
    confidence: Confidence
    explanation: str           # Plain-language explanation
    symptomatic_note: Optional[str] = None
    supporting_markers: List[str]
    citations: List[str]       # Human-readable source references
    doctor_questions: List[str]
    graph: Optional[ClinicalGraph] = None  # Knowledge graph for this pattern


class AnalysisOutput(BaseModel):
    summary: str
    patterns: List[PatternResult]
    verification_alerts: List[dict]
    disclaimer: str
    clinical_graph: Optional[ClinicalGraph] = None  # Full network graph for dashboard
