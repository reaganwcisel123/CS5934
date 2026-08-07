# Functional Requirements Specification (FRS)
## US-008 - TRIAD Signal / Clinic Needs Atlas

**Project:** CS5934 Capstone, Team 5
**Version:** 1.0 Draft
**Status:** In Progress

---

# 1. Purpose

This FRS defines the functional and non-functional requirements for the TRIAD
Signal / Clinic Needs Atlas platform. It pulls together the existing design
docs, the source code, stakeholder meetings, and product owner feedback into
one reference for what the system must do.

---

# 2. Stakeholder Input

Several discussions with project stakeholders shaped this specification.

## Product Owner Vision

The primary vision for TRIAD Signal came out of recurring meetings with
**James Pfautz**, CEO of The Authentic Consortium and Product Owner.

The goal is to give rural healthcare clinics a decision-support platform that
turns large amounts of public health data into understandable, actionable
recommendations. Rather than being another "AI dashboard," TRIAD Signal should
explain *why* a community or patient is considered high risk and recommend
practical next steps.

The product owner repeatedly described this as giving clinics a virtual
**Sherpa**: a subject matter expert that guides decision making without
replacing healthcare professionals.

---

## Meeting with Anthony Pinto (Chief Technology Officer)

A meeting with **Anthony Pinto**, CTO of The Authentic Consortium, was
especially influential. Anthony explained how the Virginia Tech capstone fits
into the larger TRIAD Signal platform and stressed a few design principles:

- Build modular components that can grow into the full platform.
- Favor explainable AI over black-box predictions.
- Make every recommendation traceable to its data source.
- Design the system to expand beyond the current prototype.

The takeaway: treat this project as the foundation for a larger rural
healthcare intelligence platform, not a standalone application.

---

# 3. Functional Requirements

The system shall:

### Data Management

- Ingest public healthcare and SDoH datasets from approved sources.
- Validate incoming datasets before processing.
- Maintain data lineage for every derived field.
- Normalize geographic identifiers using county FIPS codes.

### Data Processing

- Join community-level SDoH information with patient records.
- Generate county-level health indicators.
- Produce synthetic patient datasets without storing PHI.
- Calculate composite health need indices.

### Machine Learning

- Train county-level prediction models.
- Train synthetic patient risk models.
- Produce explainable predictions.
- Assign Low, Medium, and High risk tiers.
- Identify the primary drivers behind each prediction.
- Evaluate model fairness using rurality metrics.

### Dashboard

- Display county-level healthcare information.
- Display patient risk summaries.
- Present explainable model outputs.
- Clearly distinguish real, synthetic, and placeholder data.
- Surface relevant grant funding opportunities matched to county need
  (the Funding Matches view, fed by the Grants.gov recommender).
- Provide interactive visualizations suitable for stakeholder demonstrations.

### Virtual Assistant

- Explain county-level results.
- Answer questions using available project data only.
- Identify missing or unavailable information instead of guessing.
- Avoid providing clinical advice.

---

# 4. Non-Functional Requirements

The system shall:

- Be reproducible using documented scripts.
- Protect sensitive information by using synthetic patient data.
- Clearly identify all data sources.
- Provide transparent and explainable model outputs.
- Maintain a modular architecture for future expansion.
- Support responsible AI practices, with all model recommendations subject to
  human review.

---

# 5. Survey Integration

The Rural Healthcare Needs Assessment survey will be incorporated once
finalized. Survey findings are expected to improve intervention
recommendations, workflow priorities, feature selection, dashboard design, and
future planning. Until survey analysis is complete, related functionality
stays marked as pending (for example, the `surveyFeatures` block on synthetic
patients).

---

# 6. Future Enhancements

Stakeholder discussions raised several features that sit outside the current
prototype's scope:

- Supply forecasting
- Staffing prediction
- Referral recommendations
- Resource planning
- Expanded preventive healthcare analytics

---
