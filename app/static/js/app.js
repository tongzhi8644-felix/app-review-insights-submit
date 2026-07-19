(() => {
  const form = document.getElementById("analyze-form");
  const errEl = document.getElementById("form-error");
  const progressPanel = document.getElementById("progress-panel");
  const resultPanel = document.getElementById("result-panel");
  const progressFill = document.getElementById("progress-fill");
  const progressText = document.getElementById("progress-text");
  const stageList = document.getElementById("stage-list");
  const statusPill = document.getElementById("status-pill");
  const resultMeta = document.getElementById("result-meta");
  const tabs = document.getElementById("tabs");

  let pollTimer = null;

  if (tabs) {
    tabs.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-tab]");
      if (!btn) return;
      tabs.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  }

  if (window.__RUN_ID__) {
    progressPanel.hidden = false;
    pollRun(window.__RUN_ID__);
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errEl.hidden = true;
      const btn = document.getElementById("start-btn");
      btn.disabled = true;

      const fd = new FormData();
      const appUrl = document.getElementById("app_url").value.trim();
      const goal = document.getElementById("analysis_goal").value.trim();
      const useSample = document.getElementById("use_sample").checked;
      const file = document.getElementById("file").files[0];

      if (appUrl) fd.append("app_url", appUrl);
      fd.append("analysis_goal", goal);
      if (useSample) fd.append("use_sample", "1");
      if (file) fd.append("file", file);

      progressPanel.hidden = false;
      resultPanel.hidden = true;
      stageList.innerHTML = "";
      progressFill.style.width = "5%";
      progressText.textContent = "Starting pipeline…";

      try {
        const resp = await fetch("/api/analyze", { method: "POST", body: fd });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "Request failed");
        renderRun(data);
        if (data.status === "running") pollRun(data.id);
        history.replaceState({}, "", `/runs/${data.id}`);
      } catch (err) {
        errEl.textContent = err.message || String(err);
        errEl.hidden = false;
        progressText.textContent = "Failed to start.";
      } finally {
        btn.disabled = false;
      }
    });
  }

  function pollRun(id) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const resp = await fetch(`/api/runs/${id}`);
        const data = await resp.json();
        renderRun(data);
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(pollTimer);
        }
      } catch (_) {
        /* ignore transient poll errors */
      }
    }, 1200);
  }

  function renderRun(data) {
    progressFill.style.width = `${data.progress_pct || 0}%`;
    progressText.textContent = `${data.status} · ${data.current_stage || "-"} · ${data.progress_pct || 0}%`;
    stageList.innerHTML = (data.stage_logs || [])
      .map(
        (l) =>
          `<li class="${l.status}"><strong>${escapeHtml(l.stage)}</strong> — ${escapeHtml(
            l.message || ""
          )}</li>`
      )
      .join("");

    if (data.status === "completed" || data.result) {
      resultPanel.hidden = false;
      statusPill.textContent = data.status;
      const r = data.result || {};
      resultMeta.innerHTML = `
        <span>App ID: ${escapeHtml(data.app_id)}</span>
        <span>Source: ${escapeHtml(data.data_source || r.data_source || "-")}</span>
        <span>Evidence sufficient: ${data.evidence_sufficient ? "yes" : "no / uncertain"}</span>
        <span>Goal: ${escapeHtml(data.analysis_goal || "(none)")}</span>
      `;
      renderFindings(r.findings || []);
      renderPrd(r.prd || {});
      renderTests(r.test_cases || []);
      renderClassification(r.classifications || []);
      renderValidation(r.validation || {});
      document.getElementById("raw-json").textContent = JSON.stringify(data, null, 2);
      loadReviews(data.id);
    }

    if (data.status === "failed") {
      resultPanel.hidden = false;
      statusPill.textContent = "failed";
      resultMeta.textContent = data.error_message || "Unknown error";
    }
  }

  function renderFindings(findings) {
    const el = document.getElementById("tab-findings");
    if (!findings.length) {
      el.innerHTML = "<p class='muted'>No findings.</p>";
      return;
    }
    el.innerHTML = findings
      .map((f) => {
        const badges = [
          f.is_assumption ? "<span class='badge warn'>assumption</span>" : "",
          "<span class='badge model'>model/analysis</span>",
          `<span class='badge'>n=${f.sample_count ?? 0}</span>`,
          `<span class='badge'>conf=${formatConf(f.confidence)}</span>`,
        ].join("");
        const ids = (f.source_review_ids || []).join(", ");
        const excerpts = (f.evidence_excerpts || [])
          .map(
            (x) =>
              `<li><code>${escapeHtml(x.review_id)}</code>: ${escapeHtml(x.excerpt || "")}</li>`
          )
          .join("");
        return `<article class="finding">
          <h3>${badges}${escapeHtml(f.title || f.finding_key || "")}</h3>
          <p>${escapeHtml(f.summary || "")}</p>
          <p class="muted">Source reviews: ${escapeHtml(ids)}</p>
          ${f.uncertainty ? `<p class="muted">Uncertainty: ${escapeHtml(f.uncertainty)}</p>` : ""}
          ${
            f.conflicting_evidence
              ? `<p class="muted">Conflict: ${escapeHtml(f.conflicting_evidence)}</p>`
              : ""
          }
          ${excerpts ? `<ul>${excerpts}</ul>` : ""}
        </article>`;
      })
      .join("");
  }

  function renderPrd(prd) {
    const el = document.getElementById("tab-prd");
    const plan = (prd.version_plan || [])
      .map(
        (v) =>
          `<li><strong>${escapeHtml(v.version)}</strong> — ${escapeHtml(v.theme || "")}: ${escapeHtml(
            v.goal || ""
          )} [${escapeHtml((v.requirement_ids || []).join(", "))}]</li>`
      )
      .join("");
    const reqs = (prd.requirements || [])
      .map((r) => {
        return `<article class="req">
          <h3><span class="badge">${escapeHtml(r.priority || "")}</span>${escapeHtml(
            r.requirement_id || ""
          )}: ${escapeHtml(r.title || "")}</h3>
          <p>${escapeHtml(r.description || r.user_problem || "")}</p>
          <p class="muted">Reviews: ${escapeHtml((r.source_review_ids || []).join(", "))}</p>
        </article>`;
      })
      .join("");
    el.innerHTML = `
      <h3>Version plan</h3>
      <ul>${plan || "<li class='muted'>None</li>"}</ul>
      <h3>Requirements</h3>
      ${reqs || "<p class='muted'>None</p>"}
      <h3>PRD markdown</h3>
      <pre>${escapeHtml(prd.prd_markdown || "")}</pre>
    `;
  }

  function renderTests(cases) {
    const el = document.getElementById("tab-tests");
    if (!cases.length) {
      el.innerHTML = "<p class='muted'>No test cases.</p>";
      return;
    }
    el.innerHTML = cases
      .map((tc) => {
        const steps = (tc.steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
        return `<article class="tc">
          <h3>${escapeHtml(tc.case_id || "")}: ${escapeHtml(tc.title || "")}</h3>
          <p class="muted">Requirement: ${escapeHtml(tc.requirement_id || "")}</p>
          <ol>${steps}</ol>
          <p><strong>Expected:</strong> ${escapeHtml(tc.expected_result || "")}</p>
          <p class="muted">Reviews: ${escapeHtml((tc.source_review_ids || []).join(", "))}</p>
        </article>`;
      })
      .join("");
  }

  function renderClassification(rows) {
    const el = document.getElementById("tab-classification");
    if (!rows.length) {
      el.innerHTML = "<p class='muted'>No classification rows.</p>";
      return;
    }
    const body = rows
      .slice(0, 200)
      .map(
        (c) => `<tr>
        <td>${escapeHtml(c.review_id)}</td>
        <td>${escapeHtml((c.topics || []).join(", "))}</td>
        <td>${escapeHtml(c.sentiment || "")}</td>
        <td>${escapeHtml(c.priority_hint || "")}</td>
      </tr>`
      )
      .join("");
    el.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Review</th><th>Topics</th><th>Sentiment</th><th>Priority</th></tr></thead>
      <tbody>${body}</tbody></table></div>`;
  }

  function renderValidation(v) {
    const el = document.getElementById("tab-validation");
    el.innerHTML = `
      <p>${escapeHtml(v.summary || "")}</p>
      <p>Valid chain: <strong>${v.is_valid ? "yes" : "partial / no"}</strong></p>
      <h3>Issues</h3>
      <pre>${escapeHtml(JSON.stringify(v.issues || [], null, 2))}</pre>
      <h3>Revisions</h3>
      <pre>${escapeHtml(JSON.stringify(v.revisions || [], null, 2))}</pre>
    `;
  }

  async function loadReviews(runId) {
    const el = document.getElementById("tab-reviews");
    el.innerHTML = "<p class='muted'>Loading reviews…</p>";
    try {
      const [raw, clean] = await Promise.all([
        fetch(`/api/runs/${runId}/reviews/raw`).then((r) => r.json()),
        fetch(`/api/runs/${runId}/reviews/clean`).then((r) => r.json()),
      ]);
      el.innerHTML = `
        <h3>Raw (${raw.length})</h3>
        ${reviewTable(raw)}
        <h3>Cleaned (${clean.length})</h3>
        ${reviewTable(clean)}
      `;
    } catch (e) {
      el.innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`;
    }
  }

  function reviewTable(rows) {
    const body = rows
      .slice(0, 100)
      .map(
        (r) => `<tr>
        <td>${escapeHtml(r.review_id)}</td>
        <td>${r.rating ?? ""}</td>
        <td>${escapeHtml(r.version || "")}</td>
        <td>${escapeHtml(r.title || "")}</td>
        <td>${escapeHtml((r.content || "").slice(0, 160))}</td>
      </tr>`
      )
      .join("");
    return `<div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>★</th><th>Ver</th><th>Title</th><th>Content</th></tr></thead>
      <tbody>${body}</tbody></table></div>`;
  }

  function formatConf(v) {
    if (v == null) return "-";
    return Number(v).toFixed(2);
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
