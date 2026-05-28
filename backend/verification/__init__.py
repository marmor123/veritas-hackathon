"""
Module 3: Verification Layer

Catches errors and drug interference BEFORE clinical interpretation.
Sub-modules:
  - hemolysis: pre-analytical error detection
  - drug_interference: drug-lab effect lookup
  - plausibility: physiological consistency checks
  - corrected_values: calculated/corrected values

Entry point: verify_results() in verifier.py
"""

from backend.verification.verifier import verify_results

__all__ = ["verify_results"]
