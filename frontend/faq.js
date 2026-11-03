(function () {
  "use strict";

  const CATEGORIES = [
    ["courses", "Courses"],
    ["certificates", "Certificates"],
    ["jobs", "Jobs"],
    ["account", "Account"],
  ];
  const MAX_ANSWER_LENGTH = 2000;
  const PREVIEW_LENGTH = 200;

  let entries = [];
  let editingId = null;

  function esc(value) {
    return window.ArcLite.escapeHtml(value);
  }

  function categoryLabel(value) {
    const match = CATEGORIES.find(function (pair) { return pair[0] === value; });
    return match ? match[1] : value;
  }

  function categoryOptions(selected) {
    return CATEGORIES.map(function (pair) {
      return '<option value="' + pair[0] + '"' + (pair[0] === selected ? " selected" : "") + ">" +
        pair[1] + "</option>";
    }).join("");
  }

  function preview(text) {
    return text.length > PREVIEW_LENGTH ? text.slice(0, PREVIEW_LENGTH) + "…" : text;
  }

  function formatDate(iso) {
    const date = new Date(iso);
    return isNaN(date.getTime()) ? iso : date.toLocaleString();
  }

  function render(view) {
    editingId = null;
    entries = [];
    view.innerHTML =
      "<h1>FAQ manager</h1>" +
      '<p class="muted">Add or edit the entries Arc Lite answers from. Changes are used on the next ' +
      "question, with no restart.</p>" +
      '<section aria-labelledby="form-heading">' +
        '<h2 id="form-heading">Add an entry</h2>' +
        '<form id="faq-form" class="ask-form" novalidate>' +
          '<label for="faq-category">Category</label>' +
          '<select id="faq-category" name="category">' + categoryOptions("") + "</select>" +
          '<label for="faq-keywords">Trigger keywords</label>' +
          '<input id="faq-keywords" name="keywords" type="text" ' +
            'placeholder="For example: certificate, download, get">' +
          '<span class="hint muted small">Separate keywords with commas. Use the words students are likely to type.</span>' +
          '<label for="faq-answer">Canonical answer</label>' +
          '<textarea id="faq-answer" name="canonical_answer" rows="5" maxlength="' + MAX_ANSWER_LENGTH + '"></textarea>' +
          '<span id="faq-answer-count" class="hint muted small">0 / ' + MAX_ANSWER_LENGTH + "</span>" +
          '<div class="ask-meta">' +
            '<button type="button" id="faq-cancel" class="secondary" hidden>Cancel edit</button>' +
            '<button type="submit" id="faq-save">Add entry</button>' +
          "</div>" +
          '<p id="faq-error" class="form-error" role="alert" hidden></p>' +
          '<p id="faq-success" class="notice" role="status" hidden></p>' +
        "</form>" +
      "</section>" +
      '<section aria-labelledby="list-heading">' +
        '<h2 id="list-heading">Entries</h2>' +
        '<p id="list-status" class="muted">Loading…</p>' +
        '<div class="table-wrap" id="list-wrap" hidden>' +
          "<table>" +
            "<thead><tr><th>ID</th><th>Category</th><th>Keywords</th><th>Answer</th>" +
            "<th>Updated</th><th><span class=\"sr-only\">Actions</span></th></tr></thead>" +
            '<tbody id="faq-rows"></tbody>' +
          "</table>" +
        "</div>" +
      "</section>";

    wire(view);
    load(view);
  }

  function wire(view) {
    const form = view.querySelector("#faq-form");
    const categoryEl = view.querySelector("#faq-category");
    const keywordsEl = view.querySelector("#faq-keywords");
    const answerEl = view.querySelector("#faq-answer");
    const countEl = view.querySelector("#faq-answer-count");
    const saveBtn = view.querySelector("#faq-save");
    const cancelBtn = view.querySelector("#faq-cancel");
    const errorEl = view.querySelector("#faq-error");
    const successEl = view.querySelector("#faq-success");
    const tbody = view.querySelector("#faq-rows");

    function showError(message) {
      errorEl.textContent = message;
      errorEl.hidden = !message;
    }

    function showSuccess(message) {
      successEl.textContent = message;
      successEl.hidden = !message;
    }

    function resetForm() {
      editingId = null;
      categoryEl.value = "courses";
      keywordsEl.value = "";
      answerEl.value = "";
      countEl.textContent = "0 / " + MAX_ANSWER_LENGTH;
      saveBtn.textContent = "Add entry";
      cancelBtn.hidden = true;
      showError("");
    }

    function startEdit(id) {
      const entry = entries.find(function (item) { return item.id === id; });
      if (!entry) {
        return;
      }
      editingId = id;
      categoryEl.value = entry.category;
      keywordsEl.value = entry.keywords.join(", ");
      answerEl.value = entry.canonical_answer;
      countEl.textContent = answerEl.value.length + " / " + MAX_ANSWER_LENGTH;
      saveBtn.textContent = "Save changes";
      cancelBtn.hidden = false;
      showSuccess("");
      showError("");
      form.scrollIntoView({ behavior: "smooth", block: "start" });
      categoryEl.focus();
    }

    answerEl.addEventListener("input", function () {
      countEl.textContent = answerEl.value.length + " / " + MAX_ANSWER_LENGTH;
    });

    cancelBtn.addEventListener("click", function () {
      resetForm();
      showSuccess("");
    });

    async function deleteEntry(id) {
      const confirmed = window.confirm(
        "Delete entry " + id + "? Arc Lite will stop answering from it. " +
        "Past conversations stay in the history."
      );
      if (!confirmed) {
        return;
      }

      showError("");
      showSuccess("");
      const result = await window.ArcLite.apiFetch("/admin/faq/" + id, { method: "DELETE" });
      if (!result.ok) {
        showError(result.error);
        return;
      }

      if (editingId === id) {
        resetForm();
      }
      showSuccess("Entry " + id + " deleted. Arc Lite no longer answers from it.");
      load(view);
    }

    tbody.addEventListener("click", function (event) {
      const editButton = event.target.closest("[data-edit-id]");
      if (editButton) {
        startEdit(Number(editButton.dataset.editId));
        return;
      }
      const deleteButton = event.target.closest("[data-delete-id]");
      if (deleteButton) {
        deleteEntry(Number(deleteButton.dataset.deleteId));
      }
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      showError("");
      showSuccess("");

      const category = categoryEl.value;
      const keywords = keywordsEl.value
        .split(",")
        .map(function (word) { return word.trim(); })
        .filter(Boolean);
      const answer = answerEl.value.trim();

      if (!category) {
        showError("Choose a category.");
        return;
      }
      if (keywords.length === 0) {
        showError("Add at least one keyword.");
        return;
      }
      if (!answer) {
        showError("Write the canonical answer.");
        return;
      }
      if (answer.length > MAX_ANSWER_LENGTH) {
        showError("The answer must be " + MAX_ANSWER_LENGTH + " characters or fewer.");
        return;
      }

      const isEdit = editingId !== null;
      saveBtn.disabled = true;
      saveBtn.textContent = isEdit ? "Saving…" : "Adding…";

      const result = await window.ArcLite.apiFetch(
        isEdit ? "/admin/faq/" + editingId : "/admin/faq",
        {
          method: isEdit ? "PUT" : "POST",
          body: { category: category, keywords: keywords, canonical_answer: answer },
        }
      );

      saveBtn.disabled = false;
      saveBtn.textContent = isEdit ? "Save changes" : "Add entry";

      if (!result.ok) {
        showError(result.error);
        return;
      }

      const savedId = result.data.id;
      resetForm();
      showSuccess(
        isEdit
          ? "Entry " + savedId + " updated. Arc Lite uses the change straight away."
          : "Entry " + savedId + " added. Arc Lite can answer from it now."
      );
      load(view);
    });
  }

  async function load(view) {
    const statusEl = view.querySelector("#list-status");
    const wrap = view.querySelector("#list-wrap");
    const tbody = view.querySelector("#faq-rows");

    const result = await window.ArcLite.apiFetch("/admin/faq");
    if (!result.ok) {
      statusEl.className = "form-error";
      statusEl.textContent = result.error || "Could not load the entries.";
      wrap.hidden = true;
      return;
    }

    entries = result.data.entries;
    if (entries.length === 0) {
      statusEl.className = "muted";
      statusEl.textContent = "No entries yet. Add the first one above.";
      wrap.hidden = true;
      return;
    }

    statusEl.className = "muted";
    statusEl.textContent = entries.length + (entries.length === 1 ? " entry" : " entries");
    tbody.innerHTML = entries
      .map(function (entry) {
        return "<tr>" +
          "<td>" + esc(entry.id) + "</td>" +
          "<td>" + esc(categoryLabel(entry.category)) + "</td>" +
          "<td>" + esc(entry.keywords.join(", ")) + "</td>" +
          "<td>" + esc(preview(entry.canonical_answer)) + "</td>" +
          "<td>" + esc(formatDate(entry.updated_at)) + "</td>" +
          '<td class="actions">' +
            '<button type="button" class="secondary" data-edit-id="' + esc(entry.id) + '">Edit</button>' +
            '<button type="button" class="danger" data-delete-id="' + esc(entry.id) + '">Delete</button>' +
          "</td>" +
          "</tr>";
      })
      .join("");
    wrap.hidden = false;
  }

  window.ArcPages = window.ArcPages || {};
  window.ArcPages.faq = render;
})();
