(function () {
  "use strict";

  const CATEGORY_LABELS = {
    courses: "Courses",
    certificates: "Certificates",
    jobs: "Jobs",
    account: "Account",
    none: "No category (refused)",
  };
  const PREVIEW_LENGTH = 160;

  function esc(value) {
    return window.ArcLite.escapeHtml(value);
  }

  function pct(value) {
    return Number(value).toFixed(1) + "%";
  }

  function ms(value) {
    return value === null || value === undefined ? "—" : Math.round(Number(value)) + " ms";
  }

  function formatDate(iso) {
    const date = new Date(iso);
    return isNaN(date.getTime()) ? iso : date.toLocaleString();
  }

  function preview(text) {
    return text.length > PREVIEW_LENGTH ? text.slice(0, PREVIEW_LENGTH) + "…" : text;
  }

  function card(label, value, detail) {
    return '<div class="stat-card">' +
      '<span class="stat-label">' + esc(label) + "</span>" +
      '<span class="stat-value">' + esc(value) + "</span>" +
      (detail ? '<span class="stat-detail muted small">' + esc(detail) + "</span>" : "") +
      "</div>";
  }

  // Width of each segment is a percentage computed from the API's counts.
  function verdictBar(row) {
    if (!row.total) {
      return '<span class="muted small">No conversations</span>';
    }
    const summary = "Answered " + pct(row.answered_pct) + ", unclear " + pct(row.unclear_pct) +
      ", refused " + pct(row.refused_pct);
    return '<div class="verdict-bar" role="img" aria-label="' + esc(summary) + '">' +
      '<span class="seg seg-answered" style="width:' + Number(row.answered_pct) + '%"></span>' +
      '<span class="seg seg-unclear" style="width:' + Number(row.unclear_pct) + '%"></span>' +
      '<span class="seg seg-refused" style="width:' + Number(row.refused_pct) + '%"></span>' +
      "</div>";
  }

  function renderSummary(t) {
    return '<div class="stat-grid">' +
      card("Conversations", t.conversations, "all time") +
      card("Answered", pct(t.answered_pct), t.answered + " replies") +
      card("Unclear", pct(t.unclear_pct), t.unclear + " replies") +
      card("Refused", pct(t.refused_pct), t.refused + " replies") +
      card("Average response", ms(t.avg_response_ms), "server time") +
      card("Ratings", t.rated_up + " up · " + t.rated_down + " down", "") +
      "</div>";
  }

  function renderCategories(rows) {
    const body = rows.map(function (row) {
      return "<tr>" +
        "<td>" + esc(CATEGORY_LABELS[row.category] || row.category) + "</td>" +
        "<td>" + esc(row.total) + "</td>" +
        "<td>" + verdictBar(row) + "</td>" +
        "<td>" + esc(pct(row.answered_pct)) + "</td>" +
        "<td>" + esc(pct(row.unclear_pct)) + "</td>" +
        "<td>" + esc(pct(row.refused_pct)) + "</td>" +
        "<td>" + esc(ms(row.avg_response_ms)) + "</td>" +
        "</tr>";
    }).join("");

    return "<h2>By category</h2>" +
      '<div class="legend muted small">' +
        '<span class="seg-key seg-answered"></span> Answered ' +
        '<span class="seg-key seg-unclear"></span> Unclear ' +
        '<span class="seg-key seg-refused"></span> Refused' +
      "</div>" +
      '<div class="table-wrap"><table>' +
        "<thead><tr><th>Category</th><th>Total</th><th>Verdict mix</th>" +
        "<th>Answered</th><th>Unclear</th><th>Refused</th><th>Avg response</th></tr></thead>" +
        "<tbody>" + body + "</tbody>" +
      "</table></div>";
  }

  function renderRatedDown(count, items) {
    let content;
    if (items.length === 0) {
      content = '<p class="muted">No answered replies have been rated down.</p>';
    } else {
      const rows = items.map(function (item) {
        return "<tr>" +
          "<td>" + esc(formatDate(item.created_at)) + "</td>" +
          "<td>" + esc(item.question) + "</td>" +
          "<td>" + esc(preview(item.answer)) + "</td>" +
          "<td>" + esc(CATEGORY_LABELS[item.category] || "—") + "</td>" +
          "<td>" + esc(item.matched_faq_id === null ? "—" : item.matched_faq_id) + "</td>" +
          "<td>" + esc(ms(item.response_ms)) + "</td>" +
          "</tr>";
      }).join("");
      content = '<div class="table-wrap"><table>' +
        "<thead><tr><th>When</th><th>Question</th><th>Answer shown</th><th>Category</th>" +
        "<th>FAQ entry</th><th>Response</th></tr></thead>" +
        "<tbody>" + rows + "</tbody>" +
        "</table></div>";
    }
    return "<h2>Answered but rated down (" + esc(count) + ")</h2>" +
      '<p class="muted small">Replies the chat answered confidently that a student marked as not helpful. Review these first.</p>' +
      content;
  }

  async function load(view) {
    const statusEl = view.querySelector("#stats-status");
    const content = view.querySelector("#stats-content");
    const refresh = view.querySelector("#stats-refresh");

    statusEl.className = "muted";
    statusEl.textContent = "Loading…";
    refresh.disabled = true;

    const result = await window.ArcLite.apiFetch("/admin/stats");

    refresh.disabled = false;
    if (!result.ok) {
      statusEl.className = "form-error";
      statusEl.textContent = result.error || "Could not load the dashboard.";
      content.innerHTML = "";
      return;
    }

    const data = result.data;
    statusEl.className = "muted small";
    statusEl.textContent = "Updated " + formatDate(data.generated_at);
    content.innerHTML =
      renderSummary(data.totals) +
      renderCategories(data.by_category) +
      renderRatedDown(data.answered_rated_down_count, data.answered_rated_down);
  }

  function render(view) {
    view.innerHTML =
      '<div class="page-head">' +
        "<h1>Dashboard</h1>" +
        '<button type="button" id="stats-refresh" class="secondary">Refresh</button>' +
      "</div>" +
      '<p id="stats-status" class="muted">Loading…</p>' +
      '<div id="stats-content"></div>';

    view.querySelector("#stats-refresh").addEventListener("click", function () {
      load(view);
    });
    load(view);
  }

  window.ArcPages = window.ArcPages || {};
  window.ArcPages.stats = render;
})();
