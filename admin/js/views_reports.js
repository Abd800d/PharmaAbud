/* Reports (§96) and Compare (§79–§81) views */
import { api } from "./api.js";
import { h, esc, statusBadge, emptyState, fmtDate, toast } from "./ui.js";

/* ------------------------------------------------------------- reports */
export async function renderReports(root) {
  root.innerHTML = `<div class="card"><p class="muted">Loading reports…</p></div>`;
  const catalog = await api.reports();
  root.innerHTML = `
    <div class="note">Reports (§96). Every export is audit-logged (§82). Reports reflect verification status — unverified and DEMO records are labeled.</div>
    <div class="report-grid">
      ${catalog.items.map((r) => `
        <button class="btn btn-secondary report-btn" data-id="${esc(r.id)}" title="${esc(r.description)}">${esc(r.title)}</button>
      `).join("")}
    </div>
    <div class="card" style="margin-top:14px">
      <div class="toolbar" style="justify-content:space-between">
        <h3 id="report-title">Select a report</h3>
        <button class="btn" id="report-export" disabled>Export CSV</button>
      </div>
      <div id="report-body"><p class="muted">Choose a report above to load it.</p></div>
    </div>
  `;
  let current = null;
  async function load(id, title) {
    current = id;
    root.querySelector("#report-title").textContent = title;
    root.querySelector("#report-export").disabled = false;
    root.querySelector("#report-body").innerHTML = `<p class="muted">Loading…</p>`;
    const data = await api.report(id);
    root.querySelector("#report-body").innerHTML = renderReportBody(data);
  }
  root.querySelectorAll(".report-btn").forEach((btn) => {
    btn.onclick = () => load(btn.dataset.id, btn.textContent.trim());
  });
  root.querySelector("#report-export").onclick = async () => {
    if (!current) return;
    try {
      await api.exportReportCsv(current);
      toast("Report exported (audit-logged).");
    } catch (e) {
      toast(e.message, true);
    }
  };
}

function renderReportBody(data) {
  const listKey = Object.keys(data).find((k) => Array.isArray(data[k]));
  const scalars = Object.entries(data).filter(([, v]) => !Array.isArray(v) && typeof v !== "object");
  let html = "";
  if (scalars.length) {
    html += `<div class="stat-grid">${scalars.map(([k, v]) => `
      <div class="stat"><div class="label">${esc(k.replace(/_/g, " "))}</div><div class="value">${esc(String(v))}</div></div>
    `).join("")}</div>`;
  }
  if (listKey) {
    const rows = data[listKey];
    if (!rows.length) {
      html += emptyState("No rows.");
    } else if (typeof rows[0] !== "object") {
      html += `<ul>${rows.map((v) => `<li>${esc(String(v))}</li>`).join("")}</ul>`;
    } else {
      const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
      html += `<table><thead><tr>${cols.map((c) => `<th>${esc(c.replace(/_/g, " "))}</th>`).join("")}</tr></thead>
      <tbody>${rows.slice(0, 200).map((r) => `<tr>${cols.map((c) => {
        const v = r[c];
        if (c === "verification_status" || c === "status" || c === "duplicate_kind") return `<td>${statusBadge(String(v ?? ""))}</td>`;
        if (c === "updated_at" || c === "created_at" || c === "completed_at") return `<td>${v ? fmtDate(v) : "—"}</td>`;
        if (Array.isArray(v)) return `<td>${esc(v.join(", "))}</td>`;
        return `<td>${esc(String(v ?? ""))}</td>`;
      }).join("")}</tr>`).join("")}</tbody></table>
      ${rows.length > 200 ? `<p class="muted">Showing first 200 of ${rows.length} rows — use Export CSV for the full report.</p>` : ""}`;
    }
  }
  for (const [k, v] of Object.entries(data)) {
    if (typeof v === "object" && !Array.isArray(v) && v !== null) {
      html += `<p class="muted">${esc(k)}: ${esc(JSON.stringify(v))}</p>`;
    }
  }
  return html;
}

/* ------------------------------------------------------------- compare */
export async function renderCompare(root) {
  root.innerHTML = `
    <div class="note"><strong>Comparison (§79–§81):</strong> shows differences and equivalences between records only.
    It is <strong>NOT</strong> a therapeutic recommendation and <strong>NOT</strong> substitution advice.
    “Equivalent Product” never means clinically interchangeable.</div>
    <div class="toolbar">
      <div class="cmp-pick" style="flex:1">
        <input id="cmp-a" placeholder="Search drug 1…" autocomplete="off" />
        <div class="cmp-results" id="cmp-a-results"></div>
      </div>
      <div class="cmp-pick" style="flex:1">
        <input id="cmp-b" placeholder="Search drug 2…" autocomplete="off" />
        <div class="cmp-results" id="cmp-b-results"></div>
      </div>
      <div class="cmp-pick" style="flex:1">
        <input id="cmp-c" placeholder="Optional drug 3…" autocomplete="off" />
        <div class="cmp-results" id="cmp-c-results"></div>
      </div>
      <button class="btn btn-secondary" id="cmp-clear">Clear</button>
    </div>
    <div id="cmp-out"><p class="muted">Pick at least two drugs to compare side-by-side.</p></div>
  `;

  const picked = { a: null, b: null, c: null };

  function wire(slot) {
    const input = root.querySelector(`#cmp-${slot}`);
    const results = root.querySelector(`#cmp-${slot}-results`);
    let timer = null;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = input.value.trim();
        if (q.length < 2) {
          results.innerHTML = "";
          return;
        }
        try {
          const data = await api.drugSearch(q, 6);
          const drugs = (data.items || []).filter((i) => i.kind === "drug");
          results.innerHTML = drugs.map((d) => `
            <div class="cmp-result" data-id="${esc(d.id)}" data-label="${esc(d.label || d.generic_name_en || "")}">
              ${esc(d.label || d.generic_name_en || "")} ${d.is_demo ? '<span class="badge demo">DEMO</span>' : ""}
            </div>`).join("") || `<div class="cmp-result muted">No results</div>`;
          results.querySelectorAll(".cmp-result[data-id]").forEach((el) => {
            el.onclick = () => {
              picked[slot] = { id: el.dataset.id, label: el.dataset.label };
              input.value = el.dataset.label;
              results.innerHTML = "";
              runCompare();
            };
          });
        } catch (e) {
          results.innerHTML = `<div class="cmp-result error-text">${esc(e.message)}</div>`;
        }
      }, 250);
    });
  }

  async function runCompare() {
    const ids = ["a", "b", "c"].map((s) => picked[s]).filter(Boolean);
    const out = root.querySelector("#cmp-out");
    if (ids.length < 2) {
      out.innerHTML = `<p class="muted">Pick at least two drugs to compare side-by-side.</p>`;
      return;
    }
    out.innerHTML = `<p class="muted">Comparing…</p>`;
    try {
      const data = await api.compare(ids.map((i) => i.id));
      out.innerHTML = renderCompareTable(data);
    } catch (e) {
      out.innerHTML = `<div class="card"><p class="error-text">${esc(e.message)}</p></div>`;
    }
  }

  ["a", "b", "c"].forEach(wire);
  root.querySelector("#cmp-clear").onclick = () => {
    ["a", "b", "c"].forEach((s) => {
      picked[s] = null;
      root.querySelector(`#cmp-${s}`).value = "";
      root.querySelector(`#cmp-${s}-results`).innerHTML = "";
    });
    root.querySelector("#cmp-out").innerHTML = `<p class="muted">Pick at least two drugs to compare side-by-side.</p>`;
  };
}

function renderCompareTable(data) {
  const fieldLabels = {
    generic_name_en: "Generic (EN)", generic_name_ar: "الاسم العام (AR)",
    drug_class: "Drug Class", mechanism_en: "Mechanism",
    ingredients: "Ingredients", synonyms: "Synonyms", body_systems: "Body Systems",
    dosages: "Dosages", pregnancy: "Pregnancy", interactions: "Interactions",
    side_effects: "Side Effects", source_count: "Linked Sources",
    products_count: "Products", verification_status: "Verification", is_demo: "DEMO Data",
  };
  const renderVal = (v) => {
    if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return `<span class="muted">—</span>`;
    if (typeof v === "boolean") return v ? "Yes" : "No";
    if (typeof v === "object" && !Array.isArray(v)) return esc(JSON.stringify(v));
    if (Array.isArray(v)) {
      return `<ul class="cmp-list">${v.slice(0, 6).map((item) => {
        if (typeof item === "string") return `<li>${esc(item)}</li>`;
        const label = item.text_en || item.name || item.population || item.risk_label
          || item.interacting_agent || item.code || JSON.stringify(item);
        const extra = item.severity ? ` <span class="muted">(${esc(item.severity)})</span>` : "";
        const unverified = item.is_verified === false ? ` <span class="badge warn">unverified</span>` : "";
        return `<li>${esc(String(label))}${extra}${unverified}</li>`;
      }).join("")}${v.length > 6 ? `<li class="muted">+${v.length - 6} more…</li>` : ""}</ul>`;
    }
    return esc(String(v));
  };
  return `
    <div class="card">
      <table class="cmp-table">
        <thead><tr>
          <th style="width:150px">Field</th>
          ${data.drugs.map((d) => `<th>${esc(d.label)}${d.is_demo ? ' <span class="badge demo">DEMO</span>' : ""}</th>`).join("")}
        </tr></thead>
        <tbody>
          ${data.rows.map((row) => `
            <tr class="${row.identical ? "" : "cmp-diff"}">
              <td><strong>${esc(fieldLabels[row.field] || row.field)}</strong></td>
              ${row.values.map((v) => `<td>${renderVal(v)}</td>`).join("")}
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div class="note">
      <ul>${data.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      <p class="muted">${esc(data.disclaimer_en)}</p>
    </div>
  `;
}
