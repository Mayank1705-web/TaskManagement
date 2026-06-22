// TaskFlow DS — shared API helper

const API_BASE = "http://localhost:8000";

const Api = {
  token() {
    return localStorage.getItem("tf_token");
  },

  setToken(t) {
    localStorage.setItem("tf_token", t);
  },

  setUser(u) {
    localStorage.setItem("tf_user", JSON.stringify(u));
  },

  user() {
    const raw = localStorage.getItem("tf_user");
    return raw ? JSON.parse(raw) : null;
  },

  logout() {
    localStorage.removeItem("tf_token");
    localStorage.removeItem("tf_user");
    window.location.href = "index.html";
  },

  requireAuth() {
    if (!this.token()) {
      window.location.href = "index.html";
    }
  },

  async request(path, { method = "GET", body = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = this.token();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });

    if (res.status === 401) {
      this.logout();
      throw new Error("Session expired");
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Request failed");
    }
    return data;
  },

  // Auth
  login(email, password) {
    return this.request("/api/auth/login", { method: "POST", body: { email, password } });
  },
  register(name, email, password, stack) {
    return this.request("/api/auth/register", { method: "POST", body: { name, email, password, stack } });
  },
  me() {
    return this.request("/api/auth/me");
  },
  listUsers() {
    return this.request("/api/auth/users");
  },

  // Projects
  listProjects() {
    return this.request("/api/projects");
  },
  createProject(name, description) {
    return this.request("/api/projects", { method: "POST", body: { name, description } });
  },
  listSprints(projectId) {
    return this.request(`/api/projects/${projectId}/sprints`);
  },
  createSprint(projectId, name, start_date, end_date) {
    return this.request(`/api/projects/${projectId}/sprints`, {
      method: "POST",
      body: { name, project_id: projectId, start_date, end_date },
    });
  },

  // Tasks
  listTasks(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/tasks${qs ? "?" + qs : ""}`);
  },
  myTasks() {
    return this.request("/api/tasks/my");
  },
  createTask(payload) {
    return this.request("/api/tasks", { method: "POST", body: payload });
  },
  updateTask(id, payload) {
    return this.request(`/api/tasks/${id}`, { method: "PATCH", body: payload });
  },
  deleteTask(id) {
    return this.request(`/api/tasks/${id}`, { method: "DELETE" });
  },

  // Analytics
  burndown(sprintId) {
    return this.request(`/api/analytics/burndown/${sprintId}`);
  },
  velocity(projectId) {
    return this.request(`/api/analytics/velocity/${projectId}`);
  },
  workload(projectId) {
    return this.request(`/api/analytics/workload/${projectId}`);
  },
  priorityDistribution(projectId) {
    return this.request(`/api/analytics/priority-distribution/${projectId}`);
  },

  // ML
  estimateHours(payload) {
    return this.request("/api/ml/estimate", { method: "POST", body: payload });
  },
  riskScores(projectId) {
    return this.request(`/api/ml/risk/${projectId}`);
  },
};

function chartUrl(path) {
  return `${API_BASE}${path}`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function timeAgo(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const diffMs = Date.now() - d.getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days < 0) return `due in ${Math.abs(days)}d`;
  if (days === 0) return "today";
  return `${days}d ago`;
}