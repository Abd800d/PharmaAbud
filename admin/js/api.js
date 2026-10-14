/* APH Admin API client — talks to the real FastAPI backend (§36) */
const API_BASE = "/api/v1";

function token() { return localStorage.getItem("aph_token") || ""; }

async function request(method, path, { body, form, params } = {}) {
  let url = API_BASE + path;
  if (params) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    if ([...qs].length) url += "?" + qs.toString();
  }
  const headers = {};
  if (token()) headers["Authorization"] = "Bearer " + token();
  let payload = undefined;
  if (form) {
    payload = form; // FormData — browser sets content-type
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const resp = await fetch(url, { method, headers, body: payload });
  if (resp.status === 401) {
    localStorage.removeItem("aph_token");
    localStorage.removeItem("aph_user");
    location.hash = "#/login";
    throw new Error("Session expired. Please sign in again.");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = data.error || data.detail || {};
    const message = typeof err === "string" ? err : err.message || JSON.stringify(err);
    throw new Error(message);
  }
  return data;
}

async function downloadCsv(path, params = {}) {
  let url = API_BASE + path;
  if (params) {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    if ([...qs].length) url += "?" + qs.toString();
  }
  const headers = {};
  if (token()) headers["Authorization"] = "Bearer " + token();
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const name = (cd.match(/filename=([^;]+)/) || [, "aph_export.csv"])[1].replace(/"/g, "");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const api = {
  login: (email, password) => request("POST", "/auth/login", { body: { email, password } }),
  me: () => request("GET", "/auth/me"),
  dashboard: () => request("GET", "/admin/dashboard"),
  quality: () => request("GET", "/admin/quality"),
  reviewQueue: () => request("GET", "/admin/queues/review"),
  exportData: (entity, format) => request("GET", "/admin/export", { params: { entity, format } }),

  // generic REST verbs for module-specific endpoints
  get: (path, params) => request("GET", path, { params }),
  post: (path, opts = {}) => request("POST", path, opts),
  put: (path, opts = {}) => request("PUT", path, opts),
  del: (path) => request("DELETE", path),

  search: (q, params = {}) => request("GET", "/search", { params: { q, limit: 25, ...params } }),
  drugs: (params = {}) => request("GET", "/drugs", { params }),
  drug: (id) => request("GET", "/drugs/" + id),
  createDrug: (body) => request("POST", "/drugs", { body }),
  updateDrug: (id, body) => request("PATCH", "/drugs/" + id, { body }),
  verifyDrug: (id, new_status, notes = "") => request("POST", `/drugs/${id}/verify`, { body: { new_status, notes } }),
  verificationHistory: (id) => request("GET", `/drugs/${id}/verification-history`),

  // monograph sections (§6, §90)
  putSection: (drugId, section, body) => request("PUT", `/drugs/${drugId}/${section}`, { body }),
  drugSources: (drugId) => request("GET", `/drugs/${drugId}/sources`),
  translations: (params = {}) => request("GET", "/translations", { params }),

  products: (params = {}) => request("GET", "/products", { params }),
  product: (id) => request("GET", "/products/" + id),
  createProduct: (body) => request("POST", "/products", { body }),
  verifyProduct: (id, new_status, notes = "") => request("POST", `/products/${id}/verify`, { body: { new_status, notes } }),
  productDuplicates: (id) => request("GET", `/products/${id}/duplicates`),
  equivalents: (id) => request("GET", `/products/${id}/equivalents`),
  createEquivalent: (id, targetId, why, notes = "") =>
    request("POST", `/products/${id}/equivalents`, { params: { target_product_id: targetId, why, notes } }),
  recordLinks: (params = {}) => request("GET", "/record-links", { params }),
  reviewLink: (id, decision, notes = "") =>
    request("POST", `/record-links/${id}/review`, { params: { decision, notes } }),
  deleteRecordLink: (id) => request("DELETE", `/record-links/${id}`),

  systems: () => request("GET", "/systems"),
  systemGroups: (id) => request("GET", `/systems/${id}/groups`),
  manufacturers: (params = {}) => request("GET", "/manufacturers", { params }),
  createManufacturer: (body) => request("POST", "/manufacturers", { body }),
  sources: (params = {}) => request("GET", "/sources", { params }),
  createSource: (body) => request("POST", "/sources", { body }),

  imports: (params = {}) => request("GET", "/imports", { params }),
  importUpload: (file, entityType) => {
    const form = new FormData();
    form.append("file", file);
    form.append("entity_type", entityType);
    return request("POST", "/imports/upload", { form });
  },
  importExecute: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    form.append("commit", "true");
    return request("POST", `/imports/${id}/execute-file`, { form });
  },
  importErrors: (id) => request("GET", `/imports/${id}/errors`),

  imageQueue: () => request("GET", "/images/review-queue"),
  approveImage: (id) => request("POST", `/images/${id}/approve`),
  rejectImage: (id) => request("POST", `/images/${id}/reject`),

  users: (params = {}) => request("GET", "/users", { params }),
  roles: () => request("GET", "/users/roles"),
  setUserRoles: (id, role_codes) => request("PUT", `/users/${id}/roles`, { body: { role_codes } }),
  auditLogs: (params = {}) => request("GET", "/audit-logs", { params }),
  exportAuditCsv: (params = {}) => downloadCsv("/audit-logs/export.csv", params),
  reports: () => request("GET", "/reports"),
  report: (id) => request("GET", `/reports/${id}`),
  exportReportCsv: (id) => downloadCsv(`/reports/${id}/export.csv`),
  compare: (ids) => request("GET", "/drugs/compare", { params: { ids } }),
  drugSearch: (q, limit = 8) => request("GET", "/search", { params: { q, kinds: "drug", limit } }),
};
};
