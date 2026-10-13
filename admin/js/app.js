/* APH Admin — application shell & router */
import { api } from "./api.js";
import { toast } from "./ui.js";
import { renderDashboard, renderDrugs, renderProducts } from "./views_core.js";
import { renderSystems, renderManufacturers, renderSources, renderImports, renderReview, renderImages } from "./views_data.js";
import { renderQuality, renderUsers, renderAudit } from "./views_admin.js";
import { renderReports, renderCompare } from "./views_reports.js";

const routes = {
  dashboard: { title: "Dashboard", render: renderDashboard },
  drugs: { title: "Drugs", render: renderDrugs },
  products: { title: "Products", render: renderProducts },
  compare: { title: "Compare Drugs", render: renderCompare },
  systems: { title: "Systems & Classes", render: renderSystems },
  manufacturers: { title: "Manufacturers", render: renderManufacturers },
  sources: { title: "Sources", render: renderSources },
  imports: { title: "Import Engine", render: renderImports },
  review: { title: "Review Queue", render: renderReview },
  images: { title: "Image Review", render: renderImages },
  quality: { title: "Data Quality", render: renderQuality },
  reports: { title: "Reports", render: renderReports },
  users: { title: "Users & Roles", render: renderUsers },
  audit: { title: "Audit Logs", render: renderAudit },
};

function showLogin() {
  document.getElementById("login-view").classList.remove("hidden");
  document.getElementById("shell").classList.add("hidden");
}

function showShell() {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("shell").classList.remove("hidden");
  const user = JSON.parse(localStorage.getItem("aph_user") || "{}");
  document.getElementById("user-badge").textContent = user.email || "";
}

async function navigate() {
  if (!localStorage.getItem("aph_token")) {
    showLogin();
    return;
  }
  showShell();
  const name = (location.hash.replace("#/", "") || "dashboard").split("?")[0];
  const route = routes[name] || routes.dashboard;
  document.getElementById("page-title").textContent = route.title;
  document.querySelectorAll("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === name);
  });
  const view = document.getElementById("view");
  view.innerHTML = "";
  try {
    await route.render(view);
  } catch (e) {
    view.innerHTML = `<div class="card"><p class="error-text">${e.message}</p></div>`;
  }
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");
  try {
    const data = await api.login(
      document.getElementById("login-email").value.trim(),
      document.getElementById("login-password").value,
    );
    localStorage.setItem("aph_token", data.access_token);
    const me = await api.me();
    localStorage.setItem("aph_user", JSON.stringify({ email: me.email, roles: me.roles.map((r) => r.code) }));
    location.hash = "#/dashboard";
    navigate();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
});

document.getElementById("btn-logout").addEventListener("click", () => {
  localStorage.removeItem("aph_token");
  localStorage.removeItem("aph_user");
  location.hash = "#/login";
  showLogin();
});

window.addEventListener("hashchange", navigate);
navigate();
