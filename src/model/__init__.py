"""Predictive engine (foundation): county + patient preventable-hospitalization risk.

Two baseline classifiers on a shared scaffold. The county model learns from REAL
CDC outcomes; the patient model learns a DOCUMENTED SYNTHETIC label (no real
patient outcomes exist by design -- the project is non-PHI). See documents and
`src/model/config.py` for the generative label definition.
"""
