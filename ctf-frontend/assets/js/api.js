(function () {
  const API_BASE =
    (window.CTF_CONFIG && window.CTF_CONFIG.API_BASE_URL) ||
    "http://localhost:3000/api";

  async function request(path, options) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options && options.headers ? options.headers : {}),
      },
      ...options,
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok) {
      const baseMessage = payload.message || "Request failed";
      const message = payload.error ? `${baseMessage}: ${payload.error}` : baseMessage;
      throw new Error(message);
    }

    return payload;
  }

  async function health() {
    return request("/health");
  }

  async function dbPing() {
    return request("/db/ping");
  }

  async function registerStudent(input) {
    return request("/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function loginStudent(input) {
    return request("/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function listCategories() {
    return request("/categories");
  }

  async function listChallenges(params) {
    const queryParts = [];
    if (params && params.category_id) {
      queryParts.push(`category_id=${encodeURIComponent(params.category_id)}`);
    }
    if (params && params.team_id) {
      queryParts.push(`team_id=${encodeURIComponent(params.team_id)}`);
    }
    const query = queryParts.length ? `?${queryParts.join("&")}` : "";
    return request(`/challenges${query}`);
  }

  async function getTeamProgress(teamId) {
    return request(`/teams/${teamId}/progress`);
  }

  async function listHints(challengeNo) {
    return request(`/challenges/${challengeNo}/hints`);
  }

  async function unlockHint(input) {
    return request("/hints/unlock", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function submitFlag(input) {
    return request("/submissions", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function getLeaderboard() {
    return request("/leaderboard");
  }

  async function adminCreateCategory(input) {
    return request("/admin/categories", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function adminCreateChallenge(input) {
    return request("/admin/challenges", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async function adminListSubmissions() {
    return request("/admin/submissions");
  }

  async function adminListFirstBloods() {
    return request("/admin/first-bloods");
  }

  async function adminDeleteChallenge(challengeNo) {
    return request(`/admin/challenges/${encodeURIComponent(challengeNo)}`, {
      method: "DELETE",
    });
  }

  window.CTFApi = {
    API_BASE,
    health,
    dbPing,
    registerStudent,
    loginStudent,
    listCategories,
    listChallenges,
    getTeamProgress,
    listHints,
    unlockHint,
    submitFlag,
    getLeaderboard,
    adminCreateCategory,
    adminCreateChallenge,
    adminDeleteChallenge,
    adminListSubmissions,
    adminListFirstBloods,
  };
})();
