/* Data views: Systems, Manufacturers, Sources, Imports, Review Queue, Image Review */
import { api } from "./api.js";
import { h, esc, toast, statusBadge, demoBadge, emptyState, fmtDate } from "./ui.js";

/* ------------------------------------------------------------- systems */
export async function renderSystems(root) {
  root.innerHTML = `<div class="card"><p class="muted">Loading taxonomy…</p></div>`;
  const data = await api.systems();
  root.innerHTML = `
    <div class="note info">The 18 primary medical systems (§4). Hierarchy: Body System → Therapeutic Group → Pharmacological Class → Drug → Product. Drugs may belong to several systems when scientifically justified.</div>
    <div class="card"><h3>Body Systems</h3>
      <table><thead><tr><th>#</th><th>System (EN)</th><th>النظام (AR)</th><th>Slug</th><th>Drugs</th><th></th></tr></thead>
      <tbody>${data.items.map((s) => `
        <tr>
          <td>${s.sort_order}</td>
          <td><strong>${esc(s.name_en)}</strong></td>
          <td dir="rtl">${esc(s.name_ar)}</td>
          <td><code>${esc(s.slug)}</code></td>
          <td>${s.drug_count}</td>
          <td><button class="btn btn-sm btn-secondary" data-groups="${s.id}" data-name="${esc(s.name_en)}">Groups &amp; Classes</button></td>
        </tr>`).join("")}
      </tbody></table>
    </div>
    <div class="card hidden" id="groups-card"><h3 id="groups-title"></h3><div id="groups-body"></div></div>
  `;
  root.querySelectorAll("[data-groups]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const res = await api.systemGroups(btn.dataset.groups);
      const card = root.querySelector("#groups-card");
      card.classList.remove("hidden");
      root.querySelector("#groups-title").textContent = btn.dataset.name + " — Therapeutic Groups";
      root.querySelector("#groups-body").innerHTML = res.items.length
        ? res.items.map((g) => `
          <div style="margin-bottom:14px">
            <strong>${esc(g.name_en)}</strong> <span class="muted" dir="rtl">${esc(g.name_ar)}</span>
            <div style="margin:8px 0 0 16px">
              ${(g.pharmacological_classes || []).map((c) => `
                <div class="badge" style="margin:2px">${esc(c.name_en)} · <span dir="rtl">${esc(c.name_ar)}</span></div>`).join("")}
            </div>
          </div>`).join("")
        : emptyState("No therapeutic groups yet.");
      card.scrollIntoView({ behavior: "smooth" });
    });
  });
}

/* ------------------------------------------------------------- manufacturers */
export async function renderManufacturers(root) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="manu-q" placeholder="Search manufacturer…" />
      <button class="btn btn-secondary" id="manu-search">Search</button>
      <div class="spacer"></div>
      <button class="btn btn-primary" id="manu-new">+ Add Manufacturer</button>
    </div>
    <div id="manu-form" class="card hidden">
      <h3>New Manufacturer</h3>
      <div class="form-grid">
        <label>Name (EN)<input id="mf-en" /></label>
        <label>Name (AR)<input id="mf-ar" dir="rtl" /></label>
        <label class="full">Website<input id="mf-web" placeholder="https://…" /></label>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-primary" id="mf-save">Save</button>
        <button class="btn btn-secondary" id="mf-cancel">Cancel</button>
      </div>
    </div>
    <div id="manu-list"></div>
  `;
  async function load() {
    const data = await api.manufacturers({ q: root.querySelector("#manu-q").value.trim(), limit: 50 });
    root.querySelector("#manu-list").innerHTML = data.items.length ? `
      <table><thead><tr><th>Name (EN)</th><th>الاسم</th><th>Website</th></tr></thead>
      <tbody>${data.items.map((m) => `
        <tr><td><strong>${esc(m.name_en)}</strong></td><td dir="rtl">${esc(m.name_ar)}</td><td>${esc(m.website) || "—"}</td></tr>`).join("")}
      </tbody></table>` : emptyState("No manufacturers found.");
  }
  root.querySelector("#manu-search").onclick = load;
  root.querySelector("#manu-new").onclick = () => root.querySelector("#manu-form").classList.remove("hidden");
  root.querySelector("#mf-cancel").onclick = () => root.querySelector("#manu-form").classList.add("hidden");
  root.querySelector("#mf-save").onclick = async () => {
    try {
      await api.createManufacturer({
        name_en: root.querySelector("#mf-en").value,
        name_ar: root.querySelector("#mf-ar").value,
        website: root.querySelector("#mf-web").value,
      });
      toast("Manufacturer saved.");
      root.querySelector("#manu-form").classList.add("hidden");
      load();
    } catch (e) { toast(e.message, true); }
  };
  await load();
}

/* ------------------------------------------------------------- sources */
export async function renderSources(root) {
  root.innerHTML = `
    <div class="note">Sources carry type and license metadata (§24). Authority is <strong>not uniform</strong> across sources — regulatory labels, reference works and imported data are tracked separately. Every record should reference its provenance.</div>
    <div class="toolbar">
      <button class="btn btn-primary" id="src-new">+ Register Source</button>
    </div>
    <div id="src-form" class="card hidden">
      <h3>Register Source</h3>
      <div class="form-grid">
        <label>Source Name<input id="sf-name" placeholder="e.g. DailyMed" /></label>
        <label>Type
          <select id="sf-type">
            <option value="regulatory">Regulatory agency</option>
            <option value="official_label">Official label / product info</option>
            <option value="reference">Professional reference</option>
            <option value="manufacturer">Manufacturer documentation</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label class="full">URL<input id="sf-url" placeholder="https://…" /></label>
        <label>License / usage notes<input id="sf-license" /></label>
        <label>Retrieved date<input id="sf-retrieved" placeholder="YYYY-MM-DD" /></label>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-primary" id="sf-save">Save</button>
        <button class="btn btn-secondary" id="sf-cancel">Cancel</button>
      </div>
    </div>
    <div id="src-list"></div>
  `;
  async function load() {
    const data = await api.sources({ limit: 50 });
    root.querySelector("#src-list").innerHTML = data.items.length ? `
      <table><thead><tr><th>Name</th><th>Type</th><th>URL</th><th>License</th><th>Status</th></tr></thead>
      <tbody>${data.items.map((s) => `
        <tr>
          <td><strong>${esc(s.name)}</strong> ${demoBadge(s.is_demo)}</td>
          <td>${esc(s.source_type)}</td>
          <td>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url).slice(0, 40)}…</a>` : "—"}</td>
          <td>${esc(s.license_info) || "—"}</td>
          <td>${statusBadge(s.verification_status)}</td>
        </tr>`).join("")}
      </tbody></table>` : emptyState("No sources registered.");
  }
  root.querySelector("#src-new").onclick = () => root.querySelector("#src-form").classList.remove("hidden");
  root.querySelector("#sf-cancel").onclick = () => root.querySelector("#src-form").classList.add("hidden");
  root.querySelector("#sf-save").onclick = async () => {
    try {
      await api.createSource({
        name: root.querySelector("#sf-name").value,
        source_type: root.querySelector("#sf-type").value,
        url: root.querySelector("#sf-url").value,
        license_info: root.querySelector("#sf-license").value,
        retrieved_date: root.querySelector("#sf-retrieved").value,
        is_demo: false,
      });
      toast("Source registered.");
      root.querySelector("#src-form").classList.add("hidden");
      load();
    } catch (e) { toast(e.message, true); }
  };
  await load();
}

/* ------------------------------------------------------------- imports */
export async function renderImports(root) {
  root.innerHTML = `
    <div class="note info">Import pipeline (§55): <strong>Upload → Format → Column mapping → Preview → Validation → Duplicates → Import → Review → Publish</strong>. Imported records always land in <em>pending review</em> — they are never auto-published.</div>
    <div class="steps">
      <div class="step active">1 · Upload</div><div class="step">2 · Map columns</div><div class="step">3 · Preview &amp; validate</div>
      <div class="step">4 · Duplicate report</div><div class="step">5 · Import</div><div class="step">6 · Pharmacist review</div><div class="step">7 · Publish</div>
    </div>
    <div class="card">
      <h3>Upload File</h3>
      <p class="muted">Supported: CSV, XLSX, JSON, XML, ZIP (of data files), SQLite. PostgreSQL dumps must be loaded by a DBA (see IMPORT_GUIDE.md).</p>
      <div class="toolbar" style="margin-top:12px">
        <input type="file" id="imp-file" accept=".csv,.xlsx,.json,.xml,.zip,.sqlite,.db" />
        <select id="imp-entity"><option value="product">Products</option><option value="drug">Drugs</option></select>
        <button class="btn btn-primary" id="imp-upload">Upload &amp; Preview</button>
      </div>
      <div id="imp-preview"></div>
    </div>
    <div class="card">
      <h3>Import History</h3>
      <div id="imp-list"></div>
    </div>
  `;
  async function loadHistory() {
    const data = await api.imports({ limit: 20 });
    root.querySelector("#imp-list").innerHTML = data.items.length ? `
      <table><thead><tr><th>File</th><th>Format</th><th>Status</th><th>Rows</th><th>Imported</th><th>Duplicates</th><th>Errors</th><th>Date</th><th></th></tr></thead>
      <tbody>${data.items.map((i) => `
        <tr>
          <td>${esc(i.filename)}</td><td>${esc(i.file_format)}</td><td>${statusBadge(i.status)}</td>
          <td>${i.total_rows}</td><td>${i.imported_rows}</td><td>${i.duplicate_rows}</td><td>${i.invalid_rows}</td>
          <td>${fmtDate(i.created_at)}</td>
          <td><button class="btn btn-sm btn-secondary" data-err="${i.id}">Errors</button></td>
        </tr>`).join("")}
      </tbody></table>` : emptyState("No imports yet.");
    root.querySelectorAll("[data-err]").forEach((btn) => btn.addEventListener("click", async () => {
      const res = await api.importErrors(btn.dataset.err);
      const pre = document.createElement("pre");
      pre.style.cssText = "background:#0B2545;color:#E5E7EB;padding:14px;border-radius:8px;overflow:auto;max-height:300px;font-size:12px";
      pre.textContent = res.items.length
        ? res.items.map((e) => `row ${e.row_number} · ${e.field} · ${e.value} · ${e.error}${e.suggested_correction ? " · fix: " + e.suggested_correction : ""}`).join("\n")
        : "No errors recorded.";
      const wrap = h(`<div class="card"><h3>Import Errors — export available as CSV/JSON</h3></div>`);
      wrap.appendChild(pre);
      const close = h(`<button class="btn btn-secondary" style="margin-top:10px">Close</button>`);
      close.onclick = () => wrap.remove();
      wrap.appendChild(close);
      root.querySelector("#imp-preview").appendChild(wrap);
    }));
  }

  root.querySelector("#imp-upload").onclick = async () => {
    const file = root.querySelector("#imp-file").files[0];
    if (!file) return toast("Choose a file first.", true);
    const entityType = root.querySelector("#imp-entity").value;
    const previewEl = root.querySelector("#imp-preview");
    previewEl.innerHTML = `<div class="card"><p class="muted">Uploading &amp; validating…</p></div>`;
    try {
      const preview = await api.importUpload(file, entityType);
      const importId = (preview.errors.find((e) => e.field === "_import") || {}).value;
      previewEl.innerHTML = `
        <div class="card">
          <h3>Validation Report</h3>
          <div class="stat-grid">
            <div class="stat"><div class="label">Total rows</div><div class="value">${preview.total_rows}</div></div>
            <div class="stat green"><div class="label">Valid</div><div class="value">${preview.valid_rows}</div></div>
            <div class="stat red"><div class="label">Invalid</div><div class="value">${preview.invalid_rows}</div></div>
            <div class="stat amber"><div class="label">Duplicates</div><div class="value">${preview.duplicate_rows}</div></div>
          </div>
          <p><strong>Detected columns:</strong> ${preview.columns_detected.map(esc).join(", ")}</p>
          <p><strong>Suggested mapping:</strong> <code>${esc(JSON.stringify(preview.suggested_mapping))}</code></p>
          ${preview.invalid_rows ? `<p class="muted" style="margin-top:8px">${preview.errors.filter((e) => e.field !== "_import").length} row error(s) — full report after import (CSV/JSON export).</p>` : ""}
          <div class="toolbar" style="margin-top:14px">
            <button class="btn btn-success" id="imp-commit">Import into Pending Review</button>
          </div>
        </div>
        <div class="card">
          <h3>Sample Rows</h3>
          <table><thead><tr><th>#</th><th>Data</th><th>Valid</th><th>Duplicate</th></tr></thead>
          <tbody>${preview.sample_rows.map((r) => `
            <tr><td>${r.row_number}</td><td><code style="font-size:11px">${esc(JSON.stringify(r.data).slice(0, 160))}…</code></td>
            <td>${r.valid ? "✓" : "✗"}</td><td>${esc(r.duplicate_kind) || "—"}</td></tr>`).join("")}
          </tbody></table>
        </div>
      `;
      previewEl.querySelector("#imp-commit").onclick = async () => {
        try {
          const result = await api.importExecute(importId, file);
          toast(`Import complete: ${result.imported_rows} imported, ${result.duplicate_rows} duplicates flagged, ${result.invalid_rows} invalid.`);
          loadHistory();
        } catch (e) { toast(e.message, true); }
      };
    } catch (e) {
      previewEl.innerHTML = `<div class="card"><p class="error-text">${esc(e.message)}</p></div>`;
    }
  };
  await loadHistory();
}

/* ------------------------------------------------------------- review queue */
export async function renderReview(root) {
  root.innerHTML = `<div class="card"><p class="muted">Loading review queue…</p></div>`;
  const q = await api.reviewQueue();
  const section = (title, items, entity) => `
    <div class="card">
      <h3>${title} (${items.length})</h3>
      ${items.length ? `<table><thead><tr><th>Record</th><th>Status</th><th>Updated</th></tr></thead>
        <tbody>${items.map((i) => `<tr><td><strong>${esc(i.label)}</strong> ${demoBadge(i.is_demo)}</td>
        <td>${statusBadge(i.verification_status)}</td><td>${fmtDate(i.updated_at)}</td></tr>`).join("")}</tbody></table>`
        : emptyState("Queue is empty.")}
    </div>`;
  root.innerHTML = `
    <div class="note">Pharmacist review dashboard (§93). Verify only against appropriate authoritative sources. All transitions are audit-logged and versioned.</div>
    ${section("Pending Products", q.pending_products, "product")}
    ${section("Pending Drugs", q.pending_drugs, "drug")}
    ${section("Needs Update", q.needs_update, "drug")}
    <div class="card">
      <h3>Duplicate / Link Records (§16, §111)</h3>
      <p class="muted">Records are never auto-merged. Review metadata: <strong>Linked by · Why · Checked By · Approved By · Approval Date</strong>.</p>
      <div id="links-queue"></div>
    </div>
  `;
  const linksEl = root.querySelector("#links-queue");
  async function loadLinks() {
    const links = await api.recordLinks({ limit: 50 });
    linksEl.innerHTML = links.items.length ? `
      <table><thead><tr><th>Label</th><th>Records</th><th>Status</th><th>Linked By</th><th>Why</th><th>Checked By</th><th>Approved By</th><th>Approval Date</th><th></th></tr></thead>
      <tbody>${links.items.map((l) => `
        <tr>
          <td>${esc(l.label)}</td>
          <td>${esc(l.entity_a.label)} ↔ ${esc(l.entity_b.label)}</td>
          <td>${statusBadge(l.status)}</td>
          <td class="muted">${l.linked_by ? esc(l.linked_by.slice(0, 8)) + "…" : "—"}</td>
          <td class="muted" style="font-size:12px">${esc(l.why)}</td>
          <td class="muted">${l.checked_by ? esc(l.checked_by.slice(0, 8)) + "…" : "—"}</td>
          <td class="muted">${l.approved_by ? esc(l.approved_by.slice(0, 8)) + "…" : "—"}</td>
          <td>${l.approval_date ? fmtDate(l.approval_date) : "—"}</td>
          <td>${l.status === "pending" ? `
            <button class="btn btn-sm btn-success" data-lapprove="${l.id}">Approve</button>
            <button class="btn btn-sm btn-secondary" data-lreject="${l.id}">Reject</button>` : ""}</td>
        </tr>`).join("")}</tbody></table>
      <p class="muted" style="margin-top:8px">${esc(links.policy)}</p>` : emptyState("No record links yet.");
    linksEl.querySelectorAll("[data-lapprove]").forEach((b) => b.onclick = async () => {
      try { await api.reviewLink(b.dataset.lapprove, "approve"); toast("Record link approved."); loadLinks(); }
      catch (e) { toast(e.message, true); }
    });
    linksEl.querySelectorAll("[data-lreject]").forEach((b) => b.onclick = async () => {
      try { await api.reviewLink(b.dataset.lreject, "reject"); toast("Record link rejected."); loadLinks(); }
      catch (e) { toast(e.message, true); }
    });
  }
  await loadLinks();
}

/* ------------------------------------------------------------- image review */
export async function renderImages(root) {
  root.innerHTML = `<div class="card"><p class="muted">Loading image queue…</p></div>`;
  const q = await api.imageQueue();
  root.innerHTML = `
    <div class="note">Image review (§91): verify packaging authenticity, source and copyright. Approved images become the permanent product record.</div>
    <div class="card"><h3>Pending Images (${q.total})</h3>
    ${q.items.length ? `<table><thead><tr><th>Preview</th><th>Product</th><th>Kind</th><th>Size</th><th>Uploaded</th><th></th></tr></thead>
      <tbody>${q.items.map((img) => `
        <tr>
          <td><code style="font-size:11px">${esc(img.thumbnail_path || img.storage_path)}</code></td>
          <td>${esc(img.product_id.slice(0, 8))}…</td>
          <td>${esc(img.kind)}</td>
          <td>${img.width}×${img.height}</td>
          <td>${fmtDate(img.created_at)}</td>
          <td>
            <button class="btn btn-sm btn-success" data-ok="${img.id}">Approve</button>
            <button class="btn btn-sm btn-danger" data-no="${img.id}">Reject</button>
          </td>
        </tr>`).join("")}
      </tbody></table>` : emptyState("No images pending review.")}
    </div>
  `;
  root.querySelectorAll("[data-ok]").forEach((b) => b.onclick = async () => {
    await api.approveImage(b.dataset.ok); toast("Image approved."); renderImages(root);
  });
  root.querySelectorAll("[data-no]").forEach((b) => b.onclick = async () => {
    await api.rejectImage(b.dataset.no); toast("Image rejected."); renderImages(root);
  });
}
