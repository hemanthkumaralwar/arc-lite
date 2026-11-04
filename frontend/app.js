(function () {
  "use strict";

  const API_BASE = ((window.ARC_CONFIG && window.ARC_CONFIG.apiBaseUrl) || "").replace(/\/+$/, "");

  const view = document.getElementById("app");
  const apiUrlEl = document.getElementById("api-url");
  const statusEl = document.getElementById("api-status");

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Every call to the backend goes through here, so error handling is consistent.
  // Resolves to { ok, status, data, error }. It never throws.
  async function apiFetch(path, options = {}) {
    if (!API_BASE) {
      return { ok: false, status: 0, data: null, error: "The API address is not set in config.js." };
    }

    const headers = Object.assign({}, options.headers || {});
    const token = window.ArcAuth ? window.ArcAuth.token() : null;
    if (token) {
      headers["Authorization"] = "Bearer " + token;
    }
    let body;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }

    let response;
    try {
      response = await fetch(API_BASE + path, { method: options.method || "GET", headers, body });
    } catch (err) {
      return {
        ok: false,
        status: 0,
        data: null,
        error: "Could not reach the Arc Lite server at " + API_BASE + ". Check the address in config.js, " +
          "that the Render service is Live, and that CORS_ORIGINS on Render includes this website's address.",
      };
    }

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }

    // A 401 on a request that carried a token means the session has expired or was revoked.
    // A wrong password on the login request has no token, so it does not trigger this.
    if (response.status === 401 && token) {
      window.ArcAuth.signOut();
      window.ArcAuth.setNotice("Your session has ended. Please sign in again.");
      window.location.hash = "#/login";
    }

    const error = response.ok ? null : (data && data.message) || "Request failed (" + response.status + ").";
    return { ok: response.ok, status: response.status, data, error };
  }

  async function checkConnection() {
    apiUrlEl.textContent = API_BASE || "not set";
    if (!API_BASE) {
      setStatus("not configured", "status-error");
      return;
    }
    const result = await apiFetch("/health");
    if (result.ok && result.data && result.data.status === "ok") {
      setStatus("connected", "status-ok");
    } else {
      setStatus("unreachable: " + (result.error || "unknown error"), "status-error");
    }
  }

  function setStatus(text, className) {
    statusEl.textContent = text;
    statusEl.className = "status " + className;
  }

  // ---- pages (placeholders; each is built in its own step) ----

  function renderPlaceholder(title, note) {
    view.innerHTML =
      "<h1>" + escapeHtml(title) + "</h1>" +
      '<p class="muted">' + escapeHtml(note) + "</p>";
  }

  // Wraps a staff-only page. A visitor who is not signed in is sent to the login page instead.
  function requireStaff(handler) {
    return function () {
      if (window.ArcAuth.isSignedIn()) {
        handler();
        return;
      }
      window.ArcAuth.setNotice("Sign in to open that page.");
      window.location.hash = "#/login";
    };
  }

  const routes = {
    "/": function () {
      if (window.ArcPages && window.ArcPages.chat) {
        window.ArcPages.chat(view);
      } else {
        renderPlaceholder("Ask Arc Lite", "The chat page did not load. Check that chat.js is in the frontend folder.");
      }
    },
    "/login": function () {
      if (window.ArcPages && window.ArcPages.login) {
        window.ArcPages.login(view);
      } else {
        renderPlaceholder("Staff login", "The login page did not load. Check that login.js is in the frontend folder.");
      }
    },
    "/admin/faq": requireStaff(function () {
      if (window.ArcPages && window.ArcPages.faq) {
        window.ArcPages.faq(view);
      } else {
        renderPlaceholder("FAQ manager", "The FAQ manager did not load. Check that faq.js is in the frontend folder.");
      }
    }),
    "/admin/stats": requireStaff(function () {
      if (window.ArcPages && window.ArcPages.stats) {
        window.ArcPages.stats(view);
      } else {
        renderPlaceholder("Dashboard", "The dashboard did not load. Check that dashboard.js is in the frontend folder.");
      }
    }),
  };

  function currentPath() {
    const path = window.location.hash.replace(/^#/, "");
    return path || "/";
  }

  function render() {
    const handler = routes[currentPath()];
    if (handler) {
      handler();
    } else {
      renderPlaceholder("Page not found", "Choose a page from the menu above.");
    }
    window.scrollTo(0, 0);
  }

  // Shared helpers for the page steps that follow.
  window.ArcLite = { apiFetch, escapeHtml, apiBase: API_BASE };

  window.addEventListener("hashchange", render);
  render();
  checkConnection();
})();
