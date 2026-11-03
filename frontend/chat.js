(function () {
  "use strict";

  const MAX_LENGTH = 500;
  const CATEGORY_LABELS = {
    courses: "Courses",
    certificates: "Certificates",
    jobs: "Jobs",
    account: "Account",
  };
  const VERDICT_CLASSES = {
    Answered: "badge-ok",
    Unclear: "badge-warn",
    Refused: "badge-error",
  };

  function answerCardHtml(question, data) {
    const esc = window.ArcLite.escapeHtml;
    const verdictClass = VERDICT_CLASSES[data.verdict] || "badge-warn";
    const category = data.category ? CATEGORY_LABELS[data.category] || data.category : "No category";
    return (
      '<p class="question-text"><strong>You asked:</strong> ' + esc(question) + "</p>" +
      '<div class="badges">' +
        '<span class="badge ' + verdictClass + '">' + esc(data.verdict) + "</span>" +
        '<span class="badge badge-neutral">' + esc(category) + "</span>" +
      "</div>" +
      '<p class="answer-text">' + esc(data.answer) + "</p>" +
      '<p class="muted small">Replied in ' + esc(data.response_ms) + " ms · conversation " +
        esc(data.conversation_id) + "</p>" +
      '<div class="rating" role="group" aria-label="Was this answer helpful?">' +
        '<span class="muted small">Was this helpful?</span>' +
        '<button type="button" class="rate-btn" data-rating="up" aria-pressed="false">👍 Helpful</button>' +
        '<button type="button" class="rate-btn" data-rating="down" aria-pressed="false">👎 Not helpful</button>' +
        '<span class="rate-status small" role="status"></span>' +
      "</div>"
    );
  }

  function render(view) {
    view.innerHTML =
      "<h1>Ask Arc Lite</h1>" +
      '<p class="muted">Ask about courses, certificates, jobs, or your account. Arc Lite answers only ' +
      "from its verified FAQ, and says so when it is not sure.</p>" +
      '<form id="ask-form" class="ask-form" novalidate>' +
        '<label for="question">Your question</label>' +
        '<textarea id="question" name="question" rows="3" maxlength="' + MAX_LENGTH + '" ' +
          'placeholder="For example: How do I get my certificate?"></textarea>' +
        '<div class="ask-meta">' +
          '<span id="char-count" class="muted">0 / ' + MAX_LENGTH + "</span>" +
          '<button type="submit" id="ask-button">Ask</button>' +
        "</div>" +
        '<p id="form-error" class="form-error" role="alert" hidden></p>' +
      "</form>" +
      '<section aria-label="Answers">' +
        "<h2>Answers</h2>" +
        '<div id="answers"><p class="muted" id="empty-state">No questions yet.</p></div>' +
      "</section>";

    const form = view.querySelector("#ask-form");
    const textarea = view.querySelector("#question");
    const counter = view.querySelector("#char-count");
    const button = view.querySelector("#ask-button");
    const errorEl = view.querySelector("#form-error");
    const answers = view.querySelector("#answers");

    function showError(message) {
      errorEl.textContent = message;
      errorEl.hidden = !message;
    }

    function addAnswer(question, data) {
      const empty = answers.querySelector("#empty-state");
      if (empty) {
        empty.remove();
      }
      const card = document.createElement("article");
      card.className = "answer-card";
      card.innerHTML = answerCardHtml(question, data);
      card.dataset.conversationId = String(data.conversation_id);
      wireRating(card);
      answers.prepend(card);
    }

    function setRatingBusy(card, busy) {
      card.querySelectorAll(".rate-btn").forEach(function (btn) {
        btn.disabled = busy;
      });
    }

    function markSelected(card, rating) {
      card.querySelectorAll(".rate-btn").forEach(function (btn) {
        const selected = btn.dataset.rating === rating;
        btn.classList.toggle("selected", selected);
        btn.setAttribute("aria-pressed", selected ? "true" : "false");
      });
    }

    function wireRating(card) {
      const status = card.querySelector(".rate-status");
      card.querySelectorAll(".rate-btn").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          const rating = btn.dataset.rating;
          setRatingBusy(card, true);
          status.className = "rate-status small muted";
          status.textContent = "Saving…";

          const result = await window.ArcLite.apiFetch(
            "/chat/" + encodeURIComponent(card.dataset.conversationId) + "/rate",
            { method: "POST", body: { rating: rating } }
          );
          setRatingBusy(card, false);

          if (!result.ok) {
            status.className = "rate-status small status-error";
            status.textContent = result.error || "Could not save your feedback.";
            return;
          }

          markSelected(card, rating);
          status.className = "rate-status small status-ok";
          status.textContent = rating === "up"
            ? "Saved: marked helpful."
            : "Saved: marked not helpful.";
        });
      });
    }

    textarea.addEventListener("input", function () {
      counter.textContent = textarea.value.length + " / " + MAX_LENGTH;
    });

    // Ctrl+Enter (or Cmd+Enter on Mac) sends. Plain Enter adds a new line.
    textarea.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        form.requestSubmit();
      }
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      showError("");

      const question = textarea.value.trim();
      if (!question) {
        showError("Type a question first.");
        return;
      }
      if (question.length > MAX_LENGTH) {
        showError("Questions must be " + MAX_LENGTH + " characters or fewer.");
        return;
      }

      button.disabled = true;
      button.textContent = "Asking…";
      const result = await window.ArcLite.apiFetch("/chat", {
        method: "POST",
        body: { question: question },
      });
      button.disabled = false;
      button.textContent = "Ask";

      if (!result.ok) {
        showError(result.error);
        return;
      }

      addAnswer(question, result.data);
      textarea.value = "";
      counter.textContent = "0 / " + MAX_LENGTH;
      textarea.focus();
    });
  }

  window.ArcPages = Object.assign(window.ArcPages || {}, { chat: render });
})();
