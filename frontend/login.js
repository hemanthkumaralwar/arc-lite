(function () {
  "use strict";

  function renderSignedIn(view) {
    const esc = window.ArcLite.escapeHtml;
    view.innerHTML =
      "<h1>Signed in</h1>" +
      '<p>Signed in as <strong>' + esc(window.ArcAuth.email()) + "</strong>.</p>" +
      '<p><a href="#/admin/faq">FAQ manager</a> · <a href="#/admin/stats">Dashboard</a></p>' +
      '<p><button type="button" id="sign-out" class="secondary">Sign out</button></p>';

    view.querySelector("#sign-out").addEventListener("click", function () {
      window.ArcAuth.signOut();
      render(view);
    });
  }

  function renderForm(view) {
    const notice = window.ArcAuth.takeNotice();
    view.innerHTML =
      "<h1>Staff login</h1>" +
      (notice
        ? '<p class="notice" role="status">' + window.ArcLite.escapeHtml(notice) + "</p>"
        : "") +
      '<p class="muted">For ArchintX staff only. Staff accounts are created by the team, not on this page.</p>' +
      '<form id="login-form" class="ask-form" novalidate>' +
        '<label for="email">Email</label>' +
        '<input id="email" name="email" type="email" autocomplete="username">' +
        '<label for="password">Password</label>' +
        '<input id="password" name="password" type="password" autocomplete="current-password">' +
        '<div class="ask-meta"><span></span>' +
          '<button type="submit" id="login-button">Sign in</button>' +
        "</div>" +
        '<p id="login-error" class="form-error" role="alert" hidden></p>' +
      "</form>";

    const form = view.querySelector("#login-form");
    const emailEl = view.querySelector("#email");
    const passwordEl = view.querySelector("#password");
    const button = view.querySelector("#login-button");
    const errorEl = view.querySelector("#login-error");

    function showError(message) {
      errorEl.textContent = message;
      errorEl.hidden = !message;
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      showError("");

      const email = emailEl.value.trim();
      const password = passwordEl.value;
      if (!email || !password) {
        showError("Enter your email and password.");
        return;
      }

      button.disabled = true;
      button.textContent = "Signing in…";
      const result = await window.ArcLite.apiFetch("/auth/login", {
        method: "POST",
        body: { email: email, password: password },
      });
      button.disabled = false;
      button.textContent = "Sign in";
      passwordEl.value = "";

      if (!result.ok) {
        showError(result.error);
        passwordEl.focus();
        return;
      }

      window.ArcAuth.signIn(email.toLowerCase(), result.data.access_token);
      window.location.hash = "#/admin/faq";
    });
  }

  function render(view) {
    if (window.ArcAuth.isSignedIn()) {
      renderSignedIn(view);
    } else {
      renderForm(view);
    }
  }

  window.ArcPages = window.ArcPages || {};
  window.ArcPages.login = render;
})();
