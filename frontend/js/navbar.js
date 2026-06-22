// TaskFlow DS — shared navbar, injected into every authenticated page

function renderNavbar(activePage) {
  const user = Api.user();
  const nav = document.createElement("nav");
  nav.className = "navbar navbar-expand-lg tf-navbar";
  nav.innerHTML = `
    <div class="container-fluid">
      <a class="navbar-brand" href="dashboard.html"><span style="color:var(--tf-indigo)">●</span> TaskFlow</a>
      <div class="navbar-nav flex-row gap-3 ms-4">
        <a class="nav-link ${activePage === "dashboard" ? "active" : ""}" href="dashboard.html">Board</a>
        <a class="nav-link ${activePage === "my-tasks" ? "active" : ""}" href="my-tasks.html">My Tasks</a>
        <a class="nav-link ${activePage === "analytics" ? "active" : ""}" href="analytics.html">Analytics</a>
        <a class="nav-link ${activePage === "ml" ? "active" : ""}" href="ml.html">AI Insights</a>
        <a class="nav-link ${activePage === "tasktopus" ? "active" : ""}" href="tasktopus.html">Tasktopus</a>
      </div>
      <div class="ms-auto d-flex align-items-center gap-3">
        <span class="small text-muted">${escapeHtml(user ? user.name : "")}</span>
        <button class="btn btn-sm btn-outline-secondary" id="logoutBtn">Sign out</button>
      </div>
    </div>
  `;
  document.body.prepend(nav);
  document.getElementById("logoutBtn").addEventListener("click", () => Api.logout());
}