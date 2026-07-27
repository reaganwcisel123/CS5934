(function () {
  "use strict";

  const state = {
    records: [],
    metadata: null,
    query: "",
    tier: "all",
    sort: "risk-desc",
    selectedCountyId: null,
  };

  const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const decimalFormatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });

  function element(id) {
    return document.getElementById(id);
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    }[character]));
  }

  function riskFor(record) {
    const risk = record && record.accessFailureRisk;
    if (!risk || !isFiniteNumber(risk.probability) || risk.probability < 0 || risk.probability > 1) {
      return null;
    }
    return ["Low", "Medium", "High"].includes(risk.riskTier) ? risk : null;
  }

  function percent(value) {
    return isFiniteNumber(value) ? `${(value * 100).toFixed(1)}%` : "Not available";
  }

  function wholeNumber(value) {
    return isFiniteNumber(value) ? numberFormatter.format(value) : "Not available";
  }

  function rurality(value) {
    return isFiniteNumber(value) ? `${Math.round(value * 100)}% rurality` : "Not available";
  }

  function modelName(value) {
    if (value === "logreg") return "Logistic regression";
    if (value === "gboost") return "Histogram gradient boosting";
    return value ? escapeHtml(value) : "Not available";
  }

  function explanationName(value) {
    if (value === "logistic-coefficients") return "Logistic coefficient contributions";
    if (value === "burden-ranking") return "Deterministic burden ranking";
    return "Not available";
  }

  function featureName(value) {
    const names = {
      uninsured_percent: "Uninsured adults",
      primary_care_physician_burden: "Primary-care physician burden",
      mental_health_provider_burden: "Mental-health provider burden",
      other_primary_care_provider_burden: "Other primary-care provider burden",
      broadband_gap: "Broadband access gap",
    };
    return names[value] || value;
  }

  function tierBadge(tier) {
    const safeTier = ["High", "Medium", "Low"].includes(tier) ? tier : null;
    if (!safeTier) return "Not available";
    return `<span class="access-failure-tab__tier access-failure-tab__tier--${safeTier.toLowerCase()}">${safeTier}</span>`;
  }

  function scoredRecords() {
    return state.records.filter((record) => riskFor(record));
  }

  function selectedRecord() {
    return state.records.find((record) => record.id === state.selectedCountyId) || null;
  }

  function sortedAndFiltered(scored) {
    const query = state.query.trim().toLowerCase();
    return scored
      .filter((record) => {
        const risk = riskFor(record);
        const searchable = `${record.name || ""} ${record.id || ""}`.toLowerCase();
        return (!query || searchable.includes(query)) && (state.tier === "all" || risk.riskTier === state.tier);
      })
      .sort((left, right) => {
        const leftRisk = riskFor(left);
        const rightRisk = riskFor(right);
        if (state.sort === "risk-asc") return leftRisk.probability - rightRisk.probability;
        if (state.sort === "observed-desc") {
          const observed = (value) => isFiniteNumber(value) ? value : -Infinity;
          return observed(rightRisk.observedPreventableStays) - observed(leftRisk.observedPreventableStays);
        }
        if (state.sort === "county-asc") return String(left.name).localeCompare(String(right.name));
        return rightRisk.probability - leftRisk.probability;
      });
  }

  function renderSummary(scored, metadata) {
    const host = element("access-summary");
    const probabilities = scored.map((record) => riskFor(record).probability).sort((left, right) => left - right);
    const middle = probabilities.length ? probabilities[Math.floor(probabilities.length / 2)] : null;
    const highRisk = scored.filter((record) => riskFor(record).riskTier === "High").length;
    const performance = metadata && metadata.performance;
    const cards = [
      ["Counties displayed", wholeNumber(state.records.length)],
      ["Counties scored", wholeNumber(scored.length)],
      ["High-risk counties", wholeNumber(highRisk)],
      ["Median predicted risk", percent(middle)],
      ["Holdout PR-AUC", performance && isFiniteNumber(performance.prAuc) ? decimalFormatter.format(performance.prAuc) : "Not available"],
      ["Model data release", metadata && metadata.sourceYear ? escapeHtml(metadata.sourceYear) : "Not available"],
    ];
    host.innerHTML = cards.map(([label, value]) => `
      <div class="access-failure-tab__metric">
        <div class="access-failure-tab__label">${label}</div>
        <div class="access-failure-tab__metric-value">${value}</div>
      </div>`).join("");
  }

  function selectCounty(countyId) {
    state.selectedCountyId = countyId;
    render();
  }

  function renderTable(scored) {
    const filtered = sortedAndFiltered(scored);
    element("access-table-note").textContent =
      `${filtered.length} of ${scored.length} scored Virginia counties shown. Select a county to inspect the prediction and its reported access drivers.`;
    const body = element("access-table-body");
    if (!filtered.length) {
      body.innerHTML = "<tr><td colspan=\"5\">No scored counties match the current filters.</td></tr>";
      return;
    }
    body.innerHTML = filtered.map((record) => {
      const risk = riskFor(record);
      const selected = record.id === state.selectedCountyId ? " class=\"is-selected\"" : "";
      return `<tr${selected}>
        <td><button class="access-failure-tab__county-button" type="button" data-access-failure-county="${escapeHtml(record.id)}">${escapeHtml(record.name)} <span class="access-failure-tab__source-text">(${escapeHtml(record.id)})</span></button></td>
        <td>${percent(risk.probability)}</td>
        <td>${tierBadge(risk.riskTier)}</td>
        <td>${wholeNumber(risk.observedPreventableStays)}</td>
        <td>${rurality(record.rural)}</td>
      </tr>`;
    }).join("");
    body.querySelectorAll("[data-access-failure-county]").forEach((button) => {
      button.addEventListener("click", () => selectCounty(button.dataset.accessFailureCounty));
    });
  }

  function renderDetail() {
    const host = element("access-detail");
    const record = selectedRecord() || scoredRecords()[0] || null;
    if (!record) {
      host.innerHTML = '<div class="access-failure-tab__empty">No county record is available to review.</div>';
      return;
    }
    const risk = riskFor(record);
    if (!risk) {
      host.innerHTML = `<p class="access-failure-tab__county-name">${escapeHtml(record.name)}</p><div class="access-failure-tab__empty">Access-failure prediction is not available for this county. It is not shown as zero risk or Low risk.</div>`;
      return;
    }
    const drivers = Array.isArray(risk.topDrivers) && risk.topDrivers.length
      ? `<ul class="access-failure-tab__driver-list">${risk.topDrivers.map((driver) => `<li>${escapeHtml(driver)}</li>`).join("")}</ul>`
      : '<div class="access-failure-tab__value">Not available</div>';
    host.innerHTML = `
      <p class="access-failure-tab__county-name">${escapeHtml(record.name)} <span class="access-failure-tab__source-text">(${escapeHtml(record.id)})</span></p>
      <div class="access-failure-tab__detail-grid">
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Predicted risk</div><div class="access-failure-tab__value">${percent(risk.probability)}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Risk tier</div><div class="access-failure-tab__value">${tierBadge(risk.riskTier)}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Observed preventable stays</div><div class="access-failure-tab__value">${wholeNumber(risk.observedPreventableStays)} per 100,000</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Rurality</div><div class="access-failure-tab__value">${rurality(record.rural)}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Need index</div><div class="access-failure-tab__value">${wholeNumber(record.needIndex)}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">HPSA score</div><div class="access-failure-tab__value">${wholeNumber(record.hpsaScore)}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Model data release</div><div class="access-failure-tab__value">${escapeHtml(risk.dataYear || "Not available")}</div></div>
        <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Explanation method</div><div class="access-failure-tab__value">${explanationName(risk.explanationMethod)}</div></div>
      </div>
      <div class="access-failure-tab__detail-item"><div class="access-failure-tab__label">Top reported access drivers</div>${drivers}</div>
      <p class="access-failure-tab__source-text">Observed preventable hospital stays are an age-adjusted county indicator for Medicare fee-for-service enrollees, not a probability or a measure of every resident.</p>`;
  }

  function renderMethodology(metadata) {
    const host = element("access-methodology");
    const performance = metadata && metadata.performance;
    if (!metadata) {
      host.innerHTML = '<p class="access-failure-tab__limits">Model metadata are not available in this dataset build.</p>';
      return;
    }
    const threshold = isFiniteNumber(metadata.targetThreshold)
      ? `${wholeNumber(metadata.targetThreshold)} preventable stays per 100,000`
      : "Not available";
    const tiers = metadata.displayThresholds && isFiniteNumber(metadata.displayThresholds.high) && isFiniteNumber(metadata.displayThresholds.medium)
      ? `High at ${percent(metadata.displayThresholds.high)} or higher; Medium at ${percent(metadata.displayThresholds.medium)} or higher; otherwise Low.`
      : "Not available";
    const confusion = performance && Array.isArray(performance.confusionMatrix)
      ? performance.confusionMatrix.map((row) => Array.isArray(row) ? row.join(", ") : "").join(" / ")
      : "Not available";
    const items = [
      ["Target", metadata.targetDefinition || "Not available"],
      ["Selected model", modelName(metadata.selectedModel)],
      ["Candidate models", "Logistic regression; histogram gradient boosting"],
      ["Features", Array.isArray(metadata.features) ? metadata.features.map(featureName).join("; ") : "Not available"],
      ["Holdout PR-AUC", performance && isFiniteNumber(performance.prAuc) ? decimalFormatter.format(performance.prAuc) : "Not available"],
      ["Holdout ROC-AUC", performance && isFiniteNumber(performance.rocAuc) ? decimalFormatter.format(performance.rocAuc) : "Not available"],
      ["Brier score", performance && isFiniteNumber(performance.brierScore) ? decimalFormatter.format(performance.brierScore) : "Not available"],
      ["Positive-label prevalence", isFiniteNumber(metadata.positiveRate) ? percent(metadata.positiveRate) : "Not available"],
      ["National target threshold", threshold],
      ["Model split", metadata.nTrain && metadata.nTest ? `${wholeNumber(metadata.nTrain)} train / ${wholeNumber(metadata.nTest)} test (${escapeHtml(metadata.splitStrategy || "split strategy unavailable")})` : "Not available"],
      ["Confusion matrix", confusion],
      ["Display tiers", tiers],
    ];
    host.innerHTML = `<div class="access-failure-tab__method-grid">${items.map(([label, value]) => `
      <div class="access-failure-tab__method-item"><div class="access-failure-tab__label">${label}</div><div>${value}</div></div>`).join("")}</div>`;
  }

  function renderSource(metadata) {
    const source = element("access-source");
    const limits = element("access-limitations");
    const sourceUrl = metadata && String(metadata.sourceUrl || "").startsWith("https://") ? metadata.sourceUrl : "";
    const documentationUrl = metadata && String(metadata.documentationUrl || "").startsWith("https://") ? metadata.documentationUrl : "";
    if (!metadata || !sourceUrl) {
      source.textContent = "Official source citation is unavailable because model metadata were not included in this dataset build.";
      limits.textContent = "Limitations: Access-failure predictions are county planning signals, not individual clinical predictions. Missing counties do not receive a neutral or zero score.";
      return;
    }
    source.innerHTML = `<b>Official source:</b> <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(metadata.sourceName || "County Health Rankings & Roadmaps")}</a>${metadata.sourceRelease ? `, ${escapeHtml(metadata.sourceRelease)}` : ""}. Preventable hospital stays are used as a county-level indicator of potentially avoidable utilization and access to appropriate outpatient care.${documentationUrl ? ` <a href="${escapeHtml(documentationUrl)}" target="_blank" rel="noopener noreferrer">Data documentation</a>.` : ""}`;
    const sourceLimitation = Array.isArray(metadata.sourceLimitations) ? metadata.sourceLimitations[0] : "";
    limits.textContent = `Limitations: ${metadata.limitation || "County planning model only."} ${metadata.sourcePopulation || ""} ${sourceLimitation} Missing counties may not receive a prediction. Predicted risk is descriptive and predictive, not causal.`;
  }

  function render() {
    const scored = scoredRecords();
    const metadata = state.metadata;
    const empty = element("access-empty");
    const content = element("access-content");
    const meta = element("access-meta");
    if (!scored.length) {
      content.hidden = true;
      empty.hidden = false;
      empty.textContent = "Access-failure predictions are not available yet. Build the dataset, train the access-failure model, and rebuild the dashboard data. See the README for the exact commands.";
      meta.textContent = "";
      return;
    }
    if (!riskFor(selectedRecord())) state.selectedCountyId = scored[0].id;
    empty.hidden = true;
    content.hidden = false;
    meta.innerHTML = [
      metadata && metadata.modelVersion ? `<span><b>Model:</b> ${escapeHtml(metadata.modelVersion)}</span>` : "",
      metadata && metadata.sourceYear ? `<span><b>Data release:</b> ${escapeHtml(metadata.sourceYear)}</span>` : "",
      metadata && metadata.virginiaPredictionCount ? `<span><b>Virginia predictions:</b> ${wholeNumber(metadata.virginiaPredictionCount)}</span>` : "",
      `<span><b>Availability:</b> ${wholeNumber(scored.length)} scored, ${wholeNumber(state.records.length - scored.length)} unavailable</span>`,
    ].filter(Boolean).join("");
    renderSummary(scored, metadata);
    renderTable(scored);
    renderDetail();
    renderMethodology(metadata);
    renderSource(metadata);
  }

  function setView(view) {
    const accessIsActive = view === "access";
    element("atlas-panel").hidden = accessIsActive;
    element("access-panel").hidden = !accessIsActive;
    document.querySelectorAll("[data-access-failure-view]").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.accessFailureView === view));
    });
    if (accessIsActive) render();
  }

  function bindControls() {
    element("access-search").addEventListener("input", (event) => {
      state.query = event.target.value;
      render();
    });
    element("access-tier-filter").addEventListener("change", (event) => {
      state.tier = event.target.value;
      render();
    });
    element("access-sort").addEventListener("change", (event) => {
      state.sort = event.target.value;
      render();
    });
    const tabs = Array.from(document.querySelectorAll("[data-access-failure-view]"));
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => setView(tab.dataset.accessFailureView));
      tab.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 :
          (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next].focus();
        setView(tabs[next].dataset.accessFailureView);
      });
    });
  }

  function init(payload) {
    state.records = Array.isArray(payload && payload.records) ? payload.records : [];
    state.metadata = payload && payload.accessFailureModel ? payload.accessFailureModel : null;
    state.selectedCountyId = null;
    render();
  }

  bindControls();
  window.AccessFailureTab = { init };
}());
