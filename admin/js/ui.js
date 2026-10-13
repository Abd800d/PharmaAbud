/* Small UI helpers shared by admin views */
export function h(html) {
  const tpl = document.createElement("template");
  tpl.innerHTML = html.trim();
  return tpl.content.firstElementChild;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

export function statusBadge(status) {
  const map = {
    verified: "badge-verified",
    pending_verification: "badge-pending",
    imported_pending_review: "badge-pending",
    imported: "badge-pending",
    needs_update: "badge-pending",
    rejected: "badge-rejected",
    draft: "badge-draft",
    archived: "badge-draft",
  };
  return `<span class="badge ${map[status] || "badge-draft"}">${esc(String(status || "").replace(/_/g, " "))}</span>`;
}

export function demoBadge(isDemo) {
  return isDemo ? `<span class="badge badge-demo">DEMO</span>` : "";
}

export function barChart(rows, { green = false } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return rows.map((r) => `
    <div class="bar-row">
      <div class="bar-label">${esc(r.label)}</div>
      <div class="bar-track"><div class="bar-fill ${green ? "green" : ""}" style="width:${Math.round((r.count / max) * 100)}%"></div></div>
      <div class="bar-count">${r.count}</div>
    </div>`).join("");
}

export function emptyState(message) {
  return `<div class="empty"><p>${esc(message)}</p></div>`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
