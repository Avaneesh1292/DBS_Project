(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function showToast(message, type) {
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    if (!document.body) return;

    const safeType = String(type || "Info");
    const safeMessage = String(message || "");

    const toast = document.createElement("div");
    toast.className = "toast reveal";
    const title = document.createElement("strong");
    title.textContent = safeType;
    const content = document.createElement("div");
    content.textContent = safeMessage;
    toast.appendChild(title);
    toast.appendChild(content);
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, 2800);
  }

  function setSession(data) {
    localStorage.setItem("ctf_session", JSON.stringify(data));
  }

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem("ctf_session") || "null");
    } catch (error) {
      return null;
    }
  }

  function clearSession() {
    localStorage.removeItem("ctf_session");
  }

  function requireSession(redirectTo) {
    const session = getSession();
    if (!session && redirectTo) {
      window.location.href = redirectTo;
      return null;
    }
    return session;
  }

  function triggerHapticSuccess() {
    const splash = document.createElement("div");
    splash.className = "haptic-success-splash";
    document.body.appendChild(splash);
    setTimeout(() => splash.remove(), 700);
  }

  window.CTFCommon = {
    byId,
    showToast,
    triggerHapticSuccess,
    setSession,
    getSession,
    clearSession,
    requireSession,
  };
})();
