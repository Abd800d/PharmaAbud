/* Core views: Dashboard, Drugs, Products */
import { api } from "./api.js";
import { h, esc, toast, statusBadge, demoBadge, barChart, emptyState, fmtDate } from "./ui.js";
import { renderDrugTabs } from "./drug_tabs.js";

/* ------------------------------------------------------------- dashboard */
export async function renderDashboard(root) {
  root.innerHTML = `<div class="card"><p class="muted">Loading dashboard…</p></div>`;
  const data = await api.dashboard();
  const t = data.totals;
  root.innerHTML = `
    <div class="stat-grid">
      <div class="stat"><div class="label">Total Drugs</div><div class="value">${t.drugs}</div></div>
      <div class="stat"><div class="label">Total Products</div><div class="value">${t.products}</div></div>
      <div class="stat green"><div class="label">Verified Products</div><div class="value">${t.verified_products}</div></div>
      <div class="stat amber"><div class="label">Pending Reviews</div><div class="value">${t.pending_reviews}</div></div>
      <div class="stat"><div class="label">Manufacturers</div><div class="value">${t.manufacturers}</div></div>
      <div class="stat"><div class="label">Countries</div><div class="value">${t.countries}</div></div>
      <div class="stat"><div class="label">Images</div><div class="value">${t.images}</div></div>
      <div class="stat"><div class="label">Sources</div><div class="value">${t.sources}</div></div>
      <div class="stat red"><div class="label">Failed Imports</div><div class="value">${t.failed_imports}</div></div>
    </div>
    <div class="chart-row">
      <div class="card">
        <h3>Drugs by Body System</h3>
        ${barChart(data.charts.products_by_system.map((r) => ({ label: r.system + (r.system_ar ? ` · ${r.system_ar}` : ""), count: r.count })))}
      </div>
      <div class="card">
        <h3>Verification Status (Products)</h3>
        ${barChart(data.charts.verification_status.map((r) => ({ label: r.status.replace(/_/g, " "), count: r.count })), { green: true })}
      </div>
    </div>
    <div class="card">
      <h3>Recent Imports</h3>
      ${data.recent_imports.length ? `
        <table><thead><tr><th>File</th><th>Status</th><th>Rows</th><th>Imported</th><th>Date</th></tr></thead>
        <tbody>${data.recent_imports.map((i) => `
          <tr><td>${esc(i.filename)}</td><td>${statusBadge(i.status)}</td><td>${i.total_rows}</td><td>${i.imported_rows}</td><td>${fmtDate(i.created_at)}</td></tr>
        `).join("")}</tbody></table>` : emptyState("No imports yet")}
    </div>
    <div class="note">Data shown includes clearly-marked <strong>DEMO / DEVELOPMENT</strong> seed records. Verification status governs clinical trustworthiness — the completeness score is not a medical reliability score.</div>
  `;
}

/* ------------------------------------------------------------- drugs */
export async function renderDrugs(root) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="drug-q" placeholder="Search generic name, Arabic name, ATC…" />
      <select id="drug-status">
        <option value="">All statuses</option>
        <option value="draft">Draft</option>
        <option value="imported_pending_review">Pending review</option>
        <option value="pending_verification">Pending verification</option>
        <option value="verified">Verified</option>
        <option value="needs_update">Needs update</option>
        <option value="archived">Archived</option>
      </select>
      <button class="btn btn-secondary" id="drug-search">Search</button>
      <div class="spacer"></div>
      <button class="btn btn-primary" id="drug-new">+ New Drug</button>
    </div>
    <div id="drug-list"></div>
    <div id="drug-editor" class="hidden"></div>
  `;
  const listEl = root.querySelector("#drug-list");

  async function load() {
    const q = root.querySelector("#drug-q").value.trim();
    const status = root.querySelector("#drug-status").value;
    listEl.innerHTML = `<div class="card"><p class="muted">Loading…</p></div>`;
    const data = await api.drugs({ q, verification_status: status || undefined, limit: 50 });
    if (!data.items.length) return (listEl.innerHTML = emptyState("No drugs match this filter."));
    listEl.innerHTML = `
      <table><thead><tr><th>Generic (EN)</th><th>الاسم العربي</th><th>Class</th><th>ATC</th><th>Status</th><th>Version</th><th>Updated</th><th></th></tr></thead>
      <tbody>${data.items.map((d) => `
        <tr>
          <td><strong>${esc(d.generic_name_en)}</strong> ${demoBadge(d.is_demo)}</td>
          <td dir="rtl">${esc(d.generic_name_ar)}</td>
          <td>${esc(d.pharmacological_class_name || d.drug_class)}</td>
          <td>${esc(d.atc_code) || "—"}</td>
          <td>${statusBadge(d.verification_status)}</td>
          <td>v${d.record_version}</td>
          <td>${fmtDate(d.updated_at)}</td>
          <td><button class="btn btn-sm btn-secondary" data-edit="${d.id}">Edit</button></td>
        </tr>`).join("")}
      </tbody></table>
      <p class="muted" style="margin-top:10px">${data.total} record(s)</p>
    `;
    listEl.querySelectorAll("[data-edit]").forEach((btn) =>
      btn.addEventListener("click", () => openEditor(btn.dataset.edit)));
  }

  async function openEditor(id) {
    const editorEl = root.querySelector("#drug-editor");
    const d = id
      ? await api.drug(id)
      : { generic_name_en: "", generic_name_ar: "", mechanism_en: "", overview_en: "", is_demo: true };
    editorEl.classList.remove("hidden");
    editorEl.innerHTML = `
      <div class="card">
        <h3>${id ? `Edit: ${esc(d.generic_name_en)} ${demoBadge(d.is_demo)} ${statusBadge(d.verification_status)}` : "New Drug"}</h3>
        <div class="tabs" id="drug-tabs"></div>
        <div id="drug-tab-body"></div>
        <div class="toolbar" style="margin-top:16px">
          <button class="btn btn-primary" id="f-save">Save Draft</button>
          ${id ? `
            <button class="btn btn-secondary" data-vs="pending_verification">Submit for Verification</button>
            <button class="btn btn-success" data-vs="verified">Verify</button>
            <button class="btn btn-danger" data-vs="archived">Archive</button>` : ""}
          <div class="spacer"></div>
          <button class="btn btn-secondary" id="f-close">Close</button>
        </div>
      </div>
    `;
    if (id) {
      renderDrugTabs(editorEl.querySelector(".card"), id, d, load);
    } else {
      editorEl.querySelector("#drug-tabs").innerHTML = "<button class='active'>Basic Information</button>";
      editorEl.querySelector("#drug-tab-body").innerHTML = `
        <div class="form-grid">
          <label>Generic Name (EN)<input id="f-name-en" /></label>
          <label>Generic Name (AR)<input id="f-name-ar" dir="rtl" /></label>
          <label>Pharmacological Class<input id="f-class" /></label>
          <label>ATC Code<input id="f-atc" /></label>
          <label class="full">Mechanism (EN)<textarea id="f-mech" rows="3"></textarea></label>
        </div>`;
    }
    editorEl.querySelector("#f-close").onclick = () => editorEl.classList.add("hidden");
    editorEl.querySelector("#f-save").onclick = async () => {
      const payload = id
        ? {
            generic_name_en: editorEl.querySelector("#t-name-en")?.value || d.generic_name_en,
            generic_name_ar: editorEl.querySelector("#t-name-ar")?.value || d.generic_name_ar,
            overview_en: editorEl.querySelector("#t-overview")?.value || d.overview_en,
            mechanism_en: editorEl.querySelector("#t-mech")?.value || d.mechanism_en,
            is_demo: d.is_demo ?? true,
          }
        : {
            generic_name_en: editorEl.querySelector("#f-name-en").value,
            generic_name_ar: editorEl.querySelector("#f-name-ar").value,
            pharmacological_class_name: editorEl.querySelector("#f-class").value,
            atc_code: editorEl.querySelector("#f-atc").value,
            mechanism_en: editorEl.querySelector("#f-mech").value,
            is_demo: true,
          };
      try {
        if (id) await api.updateDrug(id, payload);
        else await api.createDrug(payload);
        toast("Saved.");
        editorEl.classList.add("hidden");
        load();
      } catch (e) { toast(e.message, true); }
    };
    editorEl.querySelectorAll("[data-vs]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          await api.verifyDrug(id, btn.dataset.vs);
          toast("Verification status updated → " + btn.dataset.vs);
          editorEl.classList.add("hidden");
          load();
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  root.querySelector("#drug-search").onclick = load;
  root.querySelector("#drug-q").addEventListener("keydown", (e) => e.key === "Enter" && load());
  root.querySelector("#drug-new").onclick = () => openEditor(null);
  await load();
}

/* ------------------------------------------------------------- products */
export async function renderProducts(root) {
  root.innerHTML = `
    <div class="note info">Products are <strong>commercial</strong> entities, strictly separate from generic drugs. Combination products carry multiple active ingredients. Equivalent products (same ingredient) are distinct from therapeutic alternatives.</div>
    <div class="toolbar">
      <input id="prod-q" placeholder="Search brand, barcode, registration…" />
      <button class="btn btn-secondary" id="prod-search">Search</button>
    </div>
    <div id="prod-list"></div>
    <div id="prod-detail" class="hidden"></div>
  `;
  const listEl = root.querySelector("#prod-list");

  async function load() {
    const q = root.querySelector("#prod-q").value.trim();
    listEl.innerHTML = `<div class="card"><p class="muted">Loading…</p></div>`;
    const data = await api.products({ q, limit: 50 });
    if (!data.items.length) return (listEl.innerHTML = emptyState("No products found."));
    listEl.innerHTML = `
      <table><thead><tr><th>Brand (EN)</th><th>الاسم التجاري</th><th>Strength</th><th>Form</th><th>Barcode</th><th>Status</th><th></th></tr></thead>
      <tbody>${data.items.map((p) => `
        <tr>
          <td><strong>${esc(p.brand_name_en)}</strong> ${demoBadge(p.is_demo)}</td>
          <td dir="rtl">${esc(p.brand_name_ar)}</td>
          <td>${esc(p.strength) || "—"}</td>
          <td>${esc(p.dosage_form) || "—"}</td>
          <td>${esc(p.barcode) || "—"}</td>
          <td>${statusBadge(p.verification_status)}</td>
          <td><button class="btn btn-sm btn-secondary" data-view="${p.id}">View</button></td>
        </tr>`).join("")}
      </tbody></table>
      <p class="muted" style="margin-top:10px">${data.total} product(s)</p>
    `;
    listEl.querySelectorAll("[data-view]").forEach((btn) => btn.addEventListener("click", () => showDetail(btn.dataset.view)));
  }

  async function showDetail(id) {
    const p = await api.product(id);
    const detailEl = root.querySelector("#prod-detail");
    detailEl.classList.remove("hidden");
    detailEl.innerHTML = `
      <div class="card">
        <h3>${esc(p.brand_name_en)} ${demoBadge(p.is_demo)} ${statusBadge(p.verification_status)}</h3>
        <div class="form-grid">
          <div><strong>Generic drug:</strong> ${p.drug ? esc(p.drug.generic_name_en) : "— (unlinked)"}</div>
          <div><strong>Strength:</strong> ${esc(p.strength) || "—"}</div>
          <div><strong>Dosage form:</strong> ${esc(p.dosage_form) || "—"}</div>
          <div><strong>Route:</strong> ${esc(p.route) || "—"}</div>
          <div><strong>Manufacturer:</strong> ${esc(p.manufacturer_name) || "—"}</div>
          <div><strong>Barcode:</strong> ${esc(p.barcode) || "—"}</div>
          <div><strong>Registration:</strong> ${esc(p.registration_number) || "—"}</div>
          <div><strong>Ingredients:</strong> ${(p.ingredients || []).map((i) => esc(i.ingredient_name_en)).join(", ") || "—"}</div>
        </div>
        <div class="toolbar" style="margin-top:16px">
          <button class="btn btn-secondary" id="p-dup">Check Duplicates</button>
          <button class="btn btn-success" data-pvs="verified">Verify</button>
          <button class="btn btn-secondary" data-pvs="pending_verification">Submit for Review</button>
          <div class="spacer"></div>
          <button class="btn btn-secondary" id="p-close">Close</button>
        </div>
        <div id="p-dup-result"></div>
        <div id="p-equiv" style="margin-top:18px"></div>
      </div>
    `;

    /* ---- Equivalent Products (§11) + link review (§111) ---- */
    async function loadEquivalents() {
      const eqEl = detailEl.querySelector("#p-equiv");
      const res = await api.equivalents(id);
      eqEl.innerHTML = `
        <h3>${esc(res.label)} (§11)</h3>
        <p class="muted">${esc(res.note)}</p>
        ${res.items.length ? `
          <table><thead><tr><th>Products</th><th>Status</th><th>Linked By</th><th>Why</th><th>Checked By</th><th>Approved By</th><th>Approval Date</th><th></th></tr></thead>
          <tbody>${res.items.map((l) => `
            <tr>
              <td>${esc(l.entity_a.label)} ↔ ${esc(l.entity_b.label)}</td>
              <td>${statusBadge(l.status)}</td>
              <td class="muted">${l.linked_by ? esc(l.linked_by.slice(0, 8)) + "…" : "—"}</td>
              <td class="muted" style="font-size:12px">${esc(l.why)}</td>
              <td class="muted">${l.checked_by ? esc(l.checked_by.slice(0, 8)) + "…" : "—"}</td>
              <td class="muted">${l.approved_by ? esc(l.approved_by.slice(0, 8)) + "…" : "—"}</td>
              <td>${l.approval_date ? fmtDate(l.approval_date) : "—"}</td>
              <td>
                ${l.status === "pending" ? `
                  <button class="btn btn-sm btn-success" data-lapprove="${l.id}">Approve</button>
                  <button class="btn btn-sm btn-secondary" data-lreject="${l.id}">Reject</button>` : ""}
                <button class="btn btn-sm btn-secondary" data-ldel="${l.id}">Remove</button>
              </td>
            </tr>`).join("")}</tbody></table>`
          : `<p class="muted">No Equivalent Product links yet.</p>`}
        <div class="toolbar" style="margin-top:10px">
          <input id="eq-target" placeholder="Target product ID or search below" style="min-width:260px" />
          <input id="eq-why" placeholder="Why (required — §111)" style="min-width:220px" />
          <button class="btn btn-primary" id="eq-add">Link as ${esc(res.label)}</button>
          <button class="btn btn-secondary" id="eq-search">Search products…</button>
        </div>
        <div id="eq-search-results"></div>
      `;
      eqEl.querySelectorAll("[data-lapprove]").forEach((b) => b.onclick = async () => {
        await api.reviewLink(b.dataset.lapprove, "approve"); toast("Equivalent Product approved."); loadEquivalents();
      });
      eqEl.querySelectorAll("[data-lreject]").forEach((b) => b.onclick = async () => {
        await api.reviewLink(b.dataset.lreject, "reject"); toast("Equivalent Product rejected."); loadEquivalents();
      });
      eqEl.querySelectorAll("[data-ldel]").forEach((b) => b.onclick = async () => {
        await api.deleteRecordLink(b.dataset.ldel); toast("Link removed."); loadEquivalents();
      });
      eqEl.querySelector("#eq-search").onclick = async () => {
        const q = eqEl.querySelector("#eq-target").value.trim();
        if (!q) return toast("Type a product name first.", true);
        const found = await api.products({ q, limit: 6 });
        eqEl.querySelector("#eq-search-results").innerHTML = found.items.length
          ? `<table><tbody>${found.items.map((p2) => `
              <tr><td><strong>${esc(p2.brand_name_en)}</strong> ${esc(p2.strength || "")}</td>
              <td><button class="btn btn-sm btn-secondary" data-pick="${p2.id}" data-label="${esc(p2.brand_name_en)}">Pick</button></td></tr>`).join("")}</tbody></table>`
          : `<p class="muted">No products match.</p>`;
        eqEl.querySelectorAll("[data-pick]").forEach((b) => b.onclick = () => {
          eqEl.querySelector("#eq-target").value = b.dataset.pick;
          eqEl.querySelector("#eq-search-results").innerHTML = "";
        });
      };
      eqEl.querySelector("#eq-add").onclick = async () => {
        const target = eqEl.querySelector("#eq-target").value.trim();
        const why = eqEl.querySelector("#eq-why").value.trim();
        if (!target || !why) return toast("Target product and 'why' are required (§111).", true);
        try {
          await api.createEquivalent(id, target, why);
          toast("Equivalent Product link created — pending review.");
          loadEquivalents();
        } catch (e) { toast(e.message, true); }
      };
    }
    await loadEquivalents();

    detailEl.querySelector("#p-close").onclick = () => detailEl.classList.add("hidden");
    detailEl.querySelector("#p-dup").onclick = async () => {
      const res = await api.productDuplicates(id);
      const out = detailEl.querySelector("#p-dup-result");
      const linksHtml = (res.links || []).length ? `
        <h4 style="margin-top:12px">Linked records (§111)</h4>
        <table><thead><tr><th>Label</th><th>Other product</th><th>Status</th><th>Linked By</th><th>Why</th><th>Checked By</th><th>Approved By</th><th>Approval Date</th></tr></thead>
        <tbody>${res.links.map((l) => `
          <tr><td>${esc(l.label)}</td><td>${esc((l.other_product_id || "").slice(0, 8))}…</td>
          <td>${statusBadge(l.status)}</td>
          <td class="muted">${l.linked_by ? esc(l.linked_by.slice(0, 8)) + "…" : "—"}</td>
          <td class="muted" style="font-size:12px">${esc(l.why)}</td>
          <td class="muted">${l.checked_by ? esc(l.checked_by.slice(0, 8)) + "…" : "—"}</td>
          <td class="muted">${l.approved_by ? esc(l.approved_by.slice(0, 8)) + "…" : "—"}</td>
          <td>${l.approval_date ? fmtDate(l.approval_date) : "—"}</td></tr>`).join("")}</tbody></table>` : "";
      out.innerHTML = (res.matches.length ? `
        <table><thead><tr><th>Kind</th><th>Product</th><th>Reasons</th><th>Confidence</th></tr></thead><tbody>
            ${res.matches.map((m) => `<tr><td>${statusBadge(m.kind)}</td><td>${esc(m.product_label)}</td><td>${m.reasons.join(", ")}</td><td>${Math.round(m.confidence * 100)}%</td></tr>`).join("")}
          </tbody></table>` : `<p class="muted" style="margin-top:10px">No duplicates detected.</p>`)
        + linksHtml + `<p class="muted" style="margin-top:8px">${esc(res.note)}</p>`;
    };
    detailEl.querySelectorAll("[data-pvs]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          await api.verifyProduct(id, btn.dataset.pvs);
          toast("Product verification updated.");
          showDetail(id);
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  root.querySelector("#prod-search").onclick = load;
  await load();
}
