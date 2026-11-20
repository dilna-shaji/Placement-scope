"""Aggregation package initialization."""
from .pipeline import AggregationPipeline
from .scam_detector import assess_opportunity_risk

__all__ = ["AggregationPipeline", "assess_opportunity_risk"]
