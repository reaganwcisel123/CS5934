# Functional Requirements Specification (FRS)
## US-008 – TRIAD Signal / Clinic Needs Atlas

**Project:** CS5934 Capstone – Team 5  
**Version:** 1.0 Draft  
**Status:** In Progress

---

# 1. Purpose

This Functional Requirements Specification (FRS) defines the functional and non-functional requirements for the TRIAD Signal / Clinic Needs Atlas platform. It consolidates existing design documentation, source code, stakeholder meetings, and product owner feedback into a single reference document describing what the system must do.

---

# 2. Stakeholder Input

Development of this specification was guided by several discussions with the project stakeholders.

## Product Owner Vision

During recurring meetings with **James Pfautz**, CEO of The Authentic Consortium and Product Owner, the primary vision for TRIAD Signal was established.

The goal is to provide rural healthcare clinics with an intelligent decision-support platform capable of transforming large amounts of public health data into understandable, actionable recommendations.

Rather than functioning as another "AI dashboard," TRIAD Signal should explain *why* a community or patient is considered high risk and recommend practical next steps.

The product owner repeatedly described this vision as providing clinics with a virtual **Sherpa** or subject matter expert that guides decision making without replacing healthcare professionals.

---

## Meeting with Anthony Pinto (Chief Technology Officer)

One of the most influential stakeholder meetings occurred when the project team met with **Anthony Pinto**, Chief Technology Officer of The Authentic Consortium.

Anthony explained how the Virginia Tech capstone fits into the larger TRIAD Signal platform and emphasized several design principles:

- Build modular components that can grow into the full platform.
- Focus on explainable AI rather than black-box predictions.
- Make every recommendation traceable to its data source.
- Design the system so it can expand beyond the current prototype.

This meeting confirmed that the current project should be treated as the foundation for a larger rural healthcare intelligence platform rather than a standalone application.

---

# 3. Functional Requirements

The system shall:

### Data Management

- Ingest public healthcare and SDoH datasets from approved sources.
- Validate incoming datasets before processing.
- Maintain data lineage for every derived field.
- Normalize geographic identifiers using County FIPS codes.

### Data Processing

- Join community-level SDoH information with patient records.
- Generate county-level health indicators.
- Produce synthetic patient datasets without storing PHI.
- Calculate composite health need indices.

### Machine Learning

The platform shall:

- Train county-level prediction models.
- Train synthetic patient risk models.
- Produce explainable predictions.
- Assign Low, Medium, and High risk tiers.
- Identify primary drivers behind each prediction.
- Evaluate model fairness using rurality metrics.

### Dashboard

The application shall:

- Display county-level healthcare information.
- Display patient risk summaries.
- Present explainable model outputs.
- Clearly distinguish real, synthetic, and placeholder data.
- Provide interactive visualizations suitable for stakeholder demonstrations.

### Virtual Assistant

The assistant shall:

- Explain county-level results.
- Answer questions using available project data.
- Identify missing or unavailable information.
- Avoid providing clinical advice.

---

# 4. Non-Functional Requirements

The system shall:

- Be reproducible using documented scripts.
- Protect sensitive information by using synthetic patient data.
- Clearly identify all data sources.
- Provide transparent and explainable model outputs.
- Maintain modular architecture for future expansion.
- Support responsible AI practices.
- Keep all model recommendations subject to human review.

---

# 5. Survey Integration

The Rural Healthcare Needs Assessment survey will be incorporated once finalized.

Survey findings are expected to improve:

- Intervention recommendations
- Workflow priorities
- Feature selection
- Dashboard design
- Future planning capabilities

Until survey analysis is completed, related functionality will remain marked as pending.

---

# 6. Future Enhancements

Based on stakeholder discussions, future versions of TRIAD Signal may include:

- Supply forecasting
- Staffing prediction
- Referral recommendations
- Resource planning
- Expanded preventive healthcare analytics

These features were discussed during stakeholder meetings but are outside the scope of the current prototype.

---