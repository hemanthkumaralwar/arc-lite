(function () {
  "use strict";

  // The token lives only in this variable. It is not written to localStorage or sessionStorage,
  // so it is gone when the page is reloaded or closed.
  let session = null;

  // A one-time message shown on the login page, for example after a redirect.
  let notice = null;

  function refreshNav() {
    const signedIn = session !== null;
    document.querySelectorAll("[data-staff-only]").forEach(function (el) {
      el.hidden = !signedIn;
    });
  }

  window.ArcAuth = {
    token: function () {
      return session ? session.token : null;
    },
    email: function () {
      return session ? session.email : null;
    },
    isSignedIn: function () {
      return session !== null;
    },
    signIn: function (email, token) {
      session = { email: email, token: token };
      refreshNav();
    },
    signOut: function () {
      session = null;
      refreshNav();
    },
    setNotice: function (text) {
      notice = text;
    },
    takeNotice: function () {
      const text = notice;
      notice = null;
      return text;
    },
  };

  refreshNav();
})();
