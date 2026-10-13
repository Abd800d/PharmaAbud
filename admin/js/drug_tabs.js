/* Drug editor tabs (§90): Clinical, Dosage, Safety, Interactions, Pregnancy,
   Lactation, Sources, Translations, Verification, Audit History.
   All connected to the real monograph API — no mock data. */
import { api } from "./api.js";
import { esc, toast, statusBadge, fmtDate } from "./ui.js";

const NOT_AVAILABLE = "Not available / Requires verified source";

export function renderDrugTabs(root, drugId, drug, onSaved) {
  const tabsEl = root.querySelector("#drug-tabs");
  const bodyEl = root.querySelector("#drug-tab-body");
  if (!tabsEl || !bodyEl) return;

  const tabs = [
    ["basic", "Basic Information"],
    ["clinical", "Clinical"],
    ["dosage", "Dosage"],
    ["safety", "Safety"],
    ["interactions", "Interactions"],
    ["pregnancy", "Pregnancy & Lactation"],
    ["sources", "Sources"],
    ["translations", "Translations"],
    ["verification", "Verification"],
    ["audit", "Audit History"],
  ];
  let active = "basic";

  function drawTabs() {
    tabsEl.innerHTML = tabs
      .map(([id, label]) => `<button data-tab="${id}" class="${id === active ? "active" : ""}">${label}</button>`)
      .join("");
    tabsEl.querySelectorAll("[data-tab]").forEach((b) => {
      b.onclick = () => { active = b.dataset.tab; drawTabs(); drawBody(); };
    });
  }

  async function drawBody() {
    bodyEl.innerHTML = `<p class="muted">Loading…</p>`;
    const d = drugId ? await api.drug(drugId) : drug;
    try {
      switch (active) {
        case "basic": bodyEl.innerHTML = await basicTab(d); wireBasic(d); break;
        case "clinical": bodyEl.innerHTML = clinicalTab(d); break;
        case "dosage": bodyEl.innerHTML = dosageTab(d); wireDosage(d); break;
        case "safety": bodyEl.innerHTML = safetyTab(d); wireSection(d, "safety"); break;
        case "interactions": bodyEl.innerHTML = interactionsTab(d); wireSection(d, "interactions"); break;
        case "pregnancy": bodyEl.innerHTML = pregnancyTab(d); wirePregnancy(d); break;
        case "sources": bodyEl.innerHTML = await sourcesTab(d); wireSources(d); break;
        case "translations": bodyEl.innerHTML = await translationsTab(d); wireTranslations(d); break;
        case "verification": bodyEl.innerHTML = await verificationTab(d); wireVerification(d); break;
        case "audit": bodyEl.innerHTML = await auditTab(d); break;
      }
    } catch (e) {
      bodyEl.innerHTML = `<p class="error-text">${esc(e.message)}</p>`;
    }
  }

  // ------------------------------------------------------------- basic
  async function basicTab(d) {
    return `
      <div class="form-grid">
        <label>Generic Name (EN)<input id="t-name-en" value="${esc(d.generic_name_en)}" /></label>
        <label>Generic Name (AR)<input id="t-name-ar" dir="rtl" value="${esc(d.generic_name_ar)}" /></label>
        <label>Drug Class<input id="t-class" value="${esc(d.drug_class || "")}" /></label>
        <label>Pharmacological Class<input id="t-pharm" value="${esc(d.pharmacological_class_name || "")}" /></label>
        <label>Therapeutic Class<input id="t-thera" value="${esc(d.therapeutic_class_name || "")}" /></label>
        <label>ATC Code<input id="t-atc" value="${esc(d.atc_code || "")}" /></label>
        <label class="full">Overview (EN)<textarea id="t-overview" rows="3">${esc(d.overview_en || "")}</textarea></label>
        <label class="full">Mechanism (EN)<textarea id="t-mech" rows="3">${esc(d.mechanism_en || "")}</textarea></label>
      </div>
      <div class="toolbar" style="margin-top:14px">
        <button class="btn btn-primary" id="t-save-basic">Save Draft</button>
      </div>`;
  }
  function wireBasic(d) {
    document.getElementById("t-save-basic").onclick = async () => {
      const payload = {
        generic_name_en: document.getElementById("t-name-en").value,
        generic_name_ar: document.getElementById("t-name-ar").value,
        drug_class: document.getElementById("t-class").value,
        pharmacological_class_name: document.getElementById("t-pharm").value,
        therapeutic_class_name: document.getElementById("t-thera").value,
        atc_code: document.getElementById("t-atc").value,
        overview_en: document.getElementById("t-overview").value,
        mechanism_en: document.getElementById("t-mech").value,
      };
      try {
        if (drugId) await api.updateDrug(drugId, payload);
        toast("Saved (audit-logged, version bumped).");
        onSaved && onSaved();
      } catch (e) { toast(e.message, true); }
    };
  }

  // ------------------------------------------------------------- clinical (read)
  function clinicalTab(d) {
    const list = (title, rows, fmt) => `
      <h4 style="margin:12px 0 6px">${title}</h4>
      ${rows.length ? `<ul style="margin-left:18px">${rows.map(fmt).join("")}</ul>` : `<p class="muted">${NOT_AVAILABLE}</p>`}`;
    return `
      ${list("Indications", d.indications || [], (i) => `<li>${esc(i.text_en)}${i.is_off_label ? ' <span class="badge badge-pending">off-label</span>' : ""}</li>`)}
      ${list("Contraindications", d.contraindications || [], (i) => `<li>${esc(i.text_en)} <span class="muted">(${esc(i.severity)})</span></li>`)}
      ${list("Warnings", d.warnings || [], (i) => `<li>${esc(i.text_en)} <span class="muted">(${esc(i.severity)})</span></li>`)}
      ${list("Precautions", d.precautions || [], (i) => `<li>${esc(i.text_en)}</li>`)}
      ${list("Adverse Effects", d.side_effects || [], (i) => `<li>${esc(i.text_en)} <span class="muted">(${esc(i.frequency || "—")}${i.is_serious ? " · serious" : ""})</span></li>`)}
      ${list("Monitoring", d.monitoring || [], (i) => `<li>${esc(i.text_en)}</li>`)}
      ${list("Administration", d.administration || [], (i) => `<li>${esc(i.text_en)}</li>`)}
      <p class="muted" style="margin-top:12px">Edit these sections in the Safety / Dosage tabs.</p>`;
  }

  // ------------------------------------------------------------- dosage
  function dosageTab(d) {
    return `
      <div class="note">Never invent doses. Unavailable entries must read exactly: <code>${NOT_AVAILABLE}</code> (§6).</div>
      <div id="dose-list">${(d.dosages || []).map((x, i) => doseRow(x, i)).join("")}</div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-secondary" id="dose-add">+ Add row</button>
        <button class="btn btn-primary" id="dose-save">Save Dosages</button>
      </div>`;
  }
  function doseRow(x = {}, i = 0) {
    return `
      <div class="form-grid dose-row" style="margin-bottom:10px; border:1px solid var(--gray-200); border-radius:8px; padding:10px">
        <label>Population
          <select class="d-pop">
            ${["adult", "pediatric", "geriatric", "renal", "hepatic"].map((p) =>
              `<option ${x.population === p ? "selected" : ""}>${p}</option>`).join("")}
          </select>
        </label>
        <label>Route<input class="d-route" value="${esc(x.route || "")}" /></label>
        <label class="full">Text (EN)<textarea class="d-text-en" rows="2">${esc(x.text_en || NOT_AVAILABLE)}</textarea></label>
        <label class="full">Text (AR)<textarea class="d-text-ar" dir="rtl" rows="2">${esc(x.text_ar || "")}</textarea></label>
        <label>Frequency<input class="d-freq" value="${esc(x.frequency || "")}" /></label>
        <label>Max dose<input class="d-max" value="${esc(x.max_dose || "")}" /></label>
      </div>`;
  }
  function wireDosage(d) {
    document.getElementById("dose-add").onclick = () => {
      document.getElementById("dose-list").insertAdjacentHTML("beforeend", doseRow({}, Date.now()));
    };
    document.getElementById("dose-save").onclick = async () => {
      const items = [...document.querySelectorAll(".dose-row")].map((row) => ({
        population: row.querySelector(".d-pop").value,
        route: row.querySelector(".d-route").value,
        text_en: row.querySelector(".d-text-en").value,
        text_ar: row.querySelector(".d-text-ar").value,
        frequency: row.querySelector(".d-freq").value,
        max_dose: row.querySelector(".d-max").value,
        is_verified: false,
      }));
      try {
        await api.putSection(drugId, "dosages", { items });
        toast("Dosages saved.");
      } catch (e) { toast(e.message, true); }
    };
  }

  // ------------------------------------------------------------- safety
  function safetyTab(d) {
    return `
      <h4>Contraindications</h4>
      <textarea id="s-contra" rows="3" placeholder="One per line">${esc((d.contraindications || []).map((x) => x.text_en).join("\n"))}</textarea>
      <h4 style="margin-top:12px">Warnings</h4>
      <textarea id="s-warn" rows="3" placeholder="One per line">${esc((d.warnings || []).map((x) => x.text_en).join("\n"))}</textarea>
      <h4 style="margin-top:12px">Precautions</h4>
      <textarea id="s-pre" rows="3" placeholder="One per line">${esc((d.precautions || []).map((x) => x.text_en).join("\n"))}</textarea>
      <h4 style="margin-top:12px">Adverse Effects</h4>
      <textarea id="s-side" rows="3" placeholder="One per line">${esc((d.side_effects || []).map((x) => x.text_en).join("\n"))}</textarea>
      <div class="toolbar" style="margin-top:14px">
        <button class="btn btn-primary" id="s-save">Save Safety Sections</button>
      </div>`;
  }

  function interactionsTab(d) {
    return `
      <h4>Drug Interactions</h4>
      <textarea id="i-drug" rows="4" placeholder="One per line (optionally 'Agent: description')">${esc((d.interactions || []).map((x) => (x.interacting_agent ? x.interacting_agent + ": " : "") + x.text_en).join("\n"))}</textarea>
      <h4 style="margin-top:12px">Food Interactions</h4>
      <textarea id="i-food" rows="3" placeholder="One per line">${esc((d.food_interactions || []).map((x) => x.text_en).join("\n"))}</textarea>
      <div class="toolbar" style="margin-top:14px">
        <button class="btn btn-primary" id="i-save">Save Interactions</button>
      </div>`;
  }

  function wireSection(d, kind) {
    const save = document.getElementById(kind === "safety" ? "s-save" : "i-save");
    if (!save) return;
    save.onclick = async () => {
      try {
        if (kind === "safety") {
          await api.putSection(drugId, "contraindications", {
            items: lines("s-contra").map((t) => ({ text_en: t, severity: "absolute" })),
          });
          await api.putSection(drugId, "warnings", {
            items: lines("s-warn").map((t) => ({ text_en: t, severity: "warning" })),
          });
          await api.putSection(drugId, "precautions", {
            items: lines("s-pre").map((t) => ({ text_en: t })),
          });
          await api.putSection(drugId, "side-effects", {
            items: lines("s-side").map((t) => ({ text_en: t })),
          });
        } else {
          await api.putSection(drugId, "interactions", {
            items: lines("i-drug").map((t) => {
              const [agent, ...rest] = t.split(":");
              return rest.length
                ? { interacting_agent: agent.trim(), text_en: rest.join(":").trim() }
                : { text_en: t };
            }),
          });
          await api.putSection(drugId, "food-interactions", {
            items: lines("i-food").map((t) => ({ text_en: t })),
          });
        }
        toast("Sections saved (audit-logged).");
      } catch (e) { toast(e.message, true); }
    };
  }
  const lines = (id) => document.getElementById(id).value.split("\n").map((s) => s.trim()).filter(Boolean);

  // ------------------------------------------------------------- pregnancy / lactation
  function pregnancyTab(d) {
    const p = d.pregnancy || {};
    const l = d.lactation || {};
    return `
      <div class="note">Preserve the source's classification terminology. Do NOT invent old FDA pregnancy categories (§6).</div>
      <h4>Pregnancy</h4>
      <div class="form-grid">
        <label class="full">Text (EN)<textarea id="p-text" rows="3">${esc(p.text_en || "")}</textarea></label>
        <label>Risk label (source wording)<input id="p-risk" value="${esc(p.risk_label || "")}" /></label>
        <label>Risk system<input id="p-system" value="${esc(p.risk_system || "")}" /></label>
        <label>Last verified date<input id="p-date" value="${esc(p.last_verified_date || "")}" placeholder="YYYY-MM-DD" /></label>
      </div>
      <h4 style="margin-top:14px">Lactation</h4>
      <div class="form-grid">
        <label class="full">Text (EN)<textarea id="l-text" rows="3">${esc(l.text_en || "")}</textarea></label>
        <label>Milk transfer<input id="l-milk" value="${esc(l.milk_transfer || "")}" /></label>
        <label>Infant considerations<input id="l-infant" value="${esc(l.infant_considerations || "")}" /></label>
      </div>
      <div class="toolbar" style="margin-top:14px">
        <button class="btn btn-primary" id="p-save">Save Pregnancy & Lactation</button>
      </div>`;
  }
  function wirePregnancy(d) {
    document.getElementById("p-save").onclick = async () => {
      try {
        await api.putSection(drugId, "pregnancy", {
          text_en: document.getElementById("p-text").value,
          risk_label: document.getElementById("p-risk").value,
          risk_system: document.getElementById("p-system").value,
          last_verified_date: document.getElementById("p-date").value,
        });
        await api.putSection(drugId, "lactation", {
          text_en: document.getElementById("l-text").value,
          milk_transfer: document.getElementById("l-milk").value,
          infant_considerations: document.getElementById("l-infant").value,
        });
        toast("Pregnancy & lactation saved.");
      } catch (e) { toast(e.message, true); }
    };
  }

  // ------------------------------------------------------------- sources
  async function sourcesTab(d) {
    const src = await api.drugSources(drugId);
    const all = await api.sources({ limit: 100 });
    return `
      <div class="note info">Field-level links (§25): Dose → Source A, Pregnancy → Source B. Prefer section-level provenance over one generic source.</div>
      <h4>Linked Sources</h4>
      ${(src.record_level || []).concat(src.field_level || []).map((s) => `
        <div class="badge" style="margin:2px">${esc(s.source_name)} — <code>${esc(s.section)}</code> <em>(${s.level})</em></div>
      `).join("") || '<p class="muted">No sources linked yet.</p>'}
      <div class="form-grid" style="margin-top:14px">
        <label>Source
          <select id="src-pick">${all.items.map((s) => `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select>
        </label>
        <label>Section<input id="src-section" placeholder="record | dosage.adult | pregnancy | mechanism" value="record" /></label>
      </div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-secondary" id="src-link-record">Link (record-level)</button>
        <button class="btn btn-primary" id="src-link-field">Link (field-level §25)</button>
      </div>`;
  }
  function wireSources(d) {
    document.getElementById("src-link-record").onclick = async () => {
      try {
        await api.post(`/drugs/${drugId}/sources`, {
          body: {
            source_id: document.getElementById("src-pick").value,
            section: document.getElementById("src-section").value || "record",
          },
        });
        toast("Source linked."); drawBody();
      } catch (e) { toast(e.message, true); }
    };
    document.getElementById("src-link-field").onclick = async () => {
      try {
        await api.post(`/drugs/${drugId}/content-sources`, {
          body: {
            source_id: document.getElementById("src-pick").value,
            section: document.getElementById("src-section").value || "record",
          },
        });
        toast("Field-level source linked."); drawBody();
      } catch (e) { toast(e.message, true); }
    };
  }

  // ------------------------------------------------------------- translations
  async function translationsTab(d) {
    const tr = await api.translations({ entity_id: drugId });
    return `
      <div class="note">Machine translations are marked and must be human-reviewed before being trusted (§58). Original source text is never overwritten (§92).</div>
      <table><thead><tr><th>Field</th><th>Lang</th><th>Original</th><th>Translation</th><th>Status</th><th></th></tr></thead>
      <tbody>${(tr.items || []).map((x) => `
        <tr>
          <td>${esc(x.field)}</td><td>${esc(x.language)}</td>
          <td>${esc(x.original_text).slice(0, 60)}</td>
          <td>${esc(x.translated_text).slice(0, 60)}</td>
          <td>${statusBadge(x.status === "human_reviewed" ? "verified" : x.status)}</td>
          <td><button class="btn btn-sm btn-success" data-approve-tr="${x.id}">Mark Reviewed</button></td>
        </tr>`).join("") || `<tr><td colspan="6" class="muted">No translation entries yet.</td></tr>`}
      </tbody></table>`;
  }
  function wireTranslations(d) {
    document.querySelectorAll("[data-approve-tr]").forEach((b) => {
      b.onclick = async () => {
        try {
          await api.post(`/translations/${b.dataset.approveTr}/approve`);
          toast("Marked as human-reviewed."); drawBody();
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  // ------------------------------------------------------------- verification
  async function verificationTab(d) {
    const hist = await api.verificationHistory(drugId);
    return `
      <div class="note">Workflow: draft → pending_verification → verified. Illegal transitions are rejected by the workflow engine (§23).</div>
      <p>Current status: ${statusBadge(d.verification_status)} · version v${d.record_version}</p>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-secondary" data-vs="pending_verification">Submit for Verification</button>
        <button class="btn btn-success" data-vs="verified">Verify</button>
        <button class="btn btn-secondary" data-vs="needs_update">Needs Update</button>
        <button class="btn btn-danger" data-vs="rejected">Reject</button>
        <button class="btn btn-secondary" data-vs="archived">Archive</button>
      </div>
      <h4 style="margin-top:16px">History</h4>
      <table><thead><tr><th>When</th><th>From</th><th>To</th><th>Reviewer</th><th>Notes</th></tr></thead>
      <tbody>${(hist || []).map((x) => `
        <tr><td>${fmtDate(x.review_date || x.created_at)}</td>
        <td>${esc(x.previous_status)}</td><td>${esc(x.new_status)}</td>
        <td>${x.reviewer_id ? esc(x.reviewer_id.slice(0, 8)) + "…" : "—"}</td>
        <td>${esc(x.notes || "")}</td></tr>`).join("")}
      </tbody></table>`;
  }
  function wireVerification(d) {
    document.querySelectorAll("[data-vs]").forEach((b) => {
      b.onclick = async () => {
        try {
          await api.verifyDrug(drugId, b.dataset.vs, "admin editor");
          toast(`Status → ${b.dataset.vs}`); drawBody(); onSaved && onSaved();
        } catch (e) { toast(e.message, true); }
      };
    });
  }

  // ------------------------------------------------------------- audit
  async function auditTab(d) {
    const logs = await api.auditLogs({ entity_type: "drug", entity_id: drugId, limit: 50 });
    return `
      <p class="muted">Append-only audit trail for this record (§29).</p>
      <table><thead><tr><th>Time</th><th>Action</th><th>User</th><th>Change</th></tr></thead>
      <tbody>${(logs.items || []).map((a) => `
        <tr><td>${fmtDate(a.timestamp)}</td><td><code>${esc(a.action)}</code></td>
        <td>${a.user_id ? esc(a.user_id.slice(0, 8)) + "…" : "—"}</td>
        <td class="muted" style="font-size:12px">${esc((a.previous_value || "").slice(0, 40))} → ${esc((a.new_value || "").slice(0, 40))}</td></tr>`).join("")}
      </tbody></table>`;
  }

  drawTabs();
  drawBody();
}
