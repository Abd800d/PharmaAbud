/* Admin views: Data Quality, Users & Roles, Audit Logs */
import { api } from "./api.js";
import { h, esc, toast, statusBadge, barChart, emptyState, fmtDate } from "./ui.js";

/* ------------------------------------------------------------- data quality */
export async function renderQuality(root) {
  root.innerHTML = `<div class="card"><p class="muted">Running quality checks…</p></div>`;
  const q = await api.quality();
  const bySeverity = { error: 0, warning: 0, info: 0 };
  q.issues.forEach((i) => { bySeverity[i.severity] = (bySeverity[i.severity] || 0) + 1; });
  root.innerHTML = `
    <div class="note">Data-quality score measures <strong>completeness only</strong> — it is explicitly NOT a medical reliability score (§57).</div>
    <div class="stat-grid">
      <div class="stat green"><div class="label">Completeness Score</div><div class="value">${q.score}</div></div>
      <div class="stat"><div class="label">Records Checked</div><div class="value">${q.total_records}</div></div>
      <div class="stat red"><div class="label">Errors</div><div class="value">${bySeverity.error}</div></div>
      <div class="stat amber"><div class="label">Warnings</div><div class="value">${bySeverity.warning}</div></div>
      <div class="stat"><div class="label">Info</div><div class="value">${bySeverity.info}</div></div>
    </div>
    <div class="chart-row">
      <div class="card">
        <h3>Issues by Type</h3>
        ${barChart(Object.entries(q.summary).map(([k, v]) => ({ label: k.replace(/_/g, " "), count: v })))}
      </div>
      <div class="card">
        <h3>Automated Checks</h3>
        <p class="muted">Missing generic name · Missing strength · Invalid dosage form · Missing manufacturer ·
        Duplicate product · Missing source · Unverified source · Missing Arabic/English translation ·
        Broken image · Invalid barcode · Conflicting classification · Expired verification</p>
      </div>
    </div>
    <div class="card">
      <h3>Actionable Issues</h3>
      ${q.issues.length ? `<table><thead><tr><th>Severity</th><th>Check</th><th>Entity</th><th>Message</th></tr></thead>
        <tbody>${q.issues.slice(0, 100).map((i) => `
          <tr>
            <td>${statusBadge(i.severity === "error" ? "rejected" : i.severity === "warning" ? "needs_update" : "draft").replace("badge-", "badge-")}</td>
            <td><code>${esc(i.code)}</code></td>
            <td>${esc(i.entity_type)} · ${esc(i.entity_label)}</td>
            <td>${esc(i.message)}</td>
          </tr>`).join("")}</tbody></table>` : emptyState("No quality issues found.")}
    </div>
  `;
}

/* ------------------------------------------------------------- users */
export async function renderUsers(root) {
  root.innerHTML = `
    <div class="note">Role-based access control (§28). Seven roles with granular permissions (drug.read … settings.manage). Role changes are audit-logged.</div>
    <div class="card"><h3>Roles</h3><div id="roles-list"></div></div>
    <div class="card"><h3>Users</h3><div id="users-list"></div></div>
    <div class="card hidden" id="roles-editor">
      <h3 id="roles-editor-title">Change Roles</h3>
      <div id="roles-checkboxes"></div>
      <div class="toolbar" style="margin-top:12px">
        <button class="btn btn-primary" id="roles-save">Save Roles</button>
        <button class="btn btn-secondary" id="roles-cancel">Cancel</button>
      </div>
    </div>
  `;
  const roles = await api.roles();
  root.querySelector("#roles-list").innerHTML = `
    <table><thead><tr><th>Code</th><th>Name (EN)</th><th>الاسم</th></tr></thead>
    <tbody>${roles.map((r) => `
      <tr><td><code>${esc(r.code)}</code></td><td>${esc(r.name_en)}</td><td dir="rtl">${esc(r.name_ar)}</td></tr>`).join("")}
    </tbody></table>`;

  const usersData = await api.users({ limit: 50 });
  let targetUser = null;
  root.querySelector("#users-list").innerHTML = usersData.items.length ? `
    <table><thead><tr><th>Email</th><th>Name</th><th>Roles</th><th>Active</th><th>Created</th><th></th></tr></thead>
    <tbody>${usersData.items.map((u) => `
      <tr>
        <td>${esc(u.email)}</td>
        <td>${esc(u.full_name) || "—"}</td>
        <td>${(u.roles || []).map((r) => `<span class="badge">${esc(r.code)}</span>`).join(" ")}</td>
        <td>${u.is_active ? "✓" : "✗"}</td>
        <td>${fmtDate(u.created_at)}</td>
        <td><button class="btn btn-sm btn-secondary" data-roles="${u.id}" data-email="${esc(u.email)}">Roles</button></td>
      </tr>`).join("")}
    </tbody></table>` : emptyState("No users.");

  root.querySelectorAll("[data-roles]").forEach((btn) => btn.addEventListener("click", () => {
    targetUser = usersData.items.find((u) => u.id === btn.dataset.roles);
    const editor = root.querySelector("#roles-editor");
    editor.classList.remove("hidden");
    root.querySelector("#roles-editor-title").textContent = "Change Roles — " + btn.dataset.email;
    const current = new Set((targetUser.roles || []).map((r) => r.code));
    root.querySelector("#roles-checkboxes").innerHTML = roles.map((r) => `
      <label style="display:inline-block;margin:4px 12px 4px 0;font-weight:600">
        <input type="checkbox" style="width:auto;margin-right:6px" value="${esc(r.code)}" ${current.has(r.code) ? "checked" : ""} />${esc(r.code)}
      </label>`).join("");
    editor.scrollIntoView({ behavior: "smooth" });
  }));

  root.querySelector("#roles-cancel").onclick = () => root.querySelector("#roles-editor").classList.add("hidden");
  root.querySelector("#roles-save").onclick = async () => {
    if (!targetUser) return;
    const codes = [...root.querySelectorAll("#roles-checkboxes input:checked")].map((i) => i.value);
    try {
      await api.setUserRoles(targetUser.id, codes);
      toast("Roles updated (audit-logged).");
      renderUsers(root);
    } catch (e) { toast(e.message, true); }
  };
}

/* ------------------------------------------------------------- audit */
export async function renderAudit(root) {
  root.innerHTML = `
    <div class="note">Append-only audit trail (§29). Ordinary users can never modify or delete these entries. Filters: action, entity type, entity id.</div>
    <div class="toolbar">
      <input id="audit-action" placeholder="action e.g. drug.updated" />
      <input id="audit-entity" placeholder="entity type e.g. drug" />
      <input id="audit-eid" placeholder="entity id" />
      <button class="btn btn-secondary" id="audit-search">Filter</button>
    </div>
    <div id="audit-list"></div>
  `;
  async function load() {
    const data = await api.auditLogs({
      action: root.querySelector("#audit-action").value.trim(),
      entity_type: root.querySelector("#audit-entity").value.trim(),
      entity_id: root.querySelector("#audit-eid").value.trim(),
      limit: 100,
    });
    root.querySelector("#audit-list").innerHTML = data.items.length ? `
      <table><thead><tr><th>Time</th><th>Action</th><th>Entity</th><th>User</th><th>Change</th></tr></thead>
      <tbody>${data.items.map((a) => `
        <tr>
          <td>${fmtDate(a.timestamp)}</td>
          <td><code>${esc(a.action)}</code></td>
          <td>${esc(a.entity_type)} ${a.entity_id ? `<span class="muted">${esc(a.entity_id.slice(0, 8))}…</span>` : ""}</td>
          <td>${a.user_id ? esc(a.user_id.slice(0, 8)) + "…" : "—"}</td>
          <td class="muted" style="font-size:12px">${esc((a.previous_value || "").slice(0, 60))} → ${esc((a.new_value || "").slice(0, 60))}</td>
        </tr>`).join("")}
      </tbody></table>
      <p class="muted" style="margin-top:10px">${esc(data.note)}</p>` : emptyState("No audit entries match.");
  }
  root.querySelector("#audit-search").onclick = load;
  await load();
}
