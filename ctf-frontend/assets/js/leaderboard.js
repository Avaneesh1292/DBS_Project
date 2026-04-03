(function () {
  const common = window.CTFCommon || {};
  const byId = typeof common.byId === "function"
    ? common.byId
    : function fallbackById(id) {
        return document.getElementById(id);
      };
  const showToast = typeof common.showToast === "function"
    ? common.showToast
    : function fallbackToast() {};
  const api = window.CTFApi || null;
  const fallbackApiBase =
    (window.CTF_CONFIG && window.CTF_CONFIG.API_BASE_URL) ||
    "http://localhost:3000/api";

  const tbody = byId("leaderboardBody");
  const refreshBtn = byId("refreshBtn");
  const statTeams = byId("statTeams");
  const statTop = byId("statTop");
  const statStatus = byId("statStatus");

  function setStatus(label, cssClass) {
    if (!statStatus) return;
    statStatus.textContent = label;
    statStatus.classList.remove("status-ok", "status-warn", "status-error");
    if (cssClass) {
      statStatus.classList.add(cssClass);
    }
  }

  function updateStats(rows) {
    if (statTeams) {
      statTeams.textContent = `${rows.length}`;
    }
    if (statTop) {
      statTop.textContent = rows.length ? `${rows[0].score ?? 0}` : "0";
    }
  }

  function normalizeRows(payload) {
    function collectCandidateArrays(value, depth) {
      if (depth > 4 || value == null) return [];

      if (Array.isArray(value)) {
        return [value];
      }

      if (typeof value !== "object") {
        return [];
      }

      const directKeys = ["leaderboard", "rows", "items", "result", "data"];
      const directCandidates = directKeys
        .map((key) => value[key])
        .filter((entry) => entry !== undefined);

      const nested = Object.keys(value).flatMap((key) => collectCandidateArrays(value[key], depth + 1));
      return directCandidates.flatMap((entry) => collectCandidateArrays(entry, depth + 1)).concat(nested);
    }

    const allArrays = collectCandidateArrays(payload, 0);
    const raw = allArrays.find(
      (arr) =>
        Array.isArray(arr) &&
        arr.some(
          (row) =>
            row &&
            typeof row === "object" &&
            ("team_name" in row || "team" in row || "name" in row || "score" in row || "points" in row)
        )
    ) || [];

    return raw
      .map((row) => ({
        team_name: String(row.team_name || row.team || row.name || "Unknown Team"),
        score: Number(row.score ?? row.points ?? 0),
      }))
      .filter((row) => Number.isFinite(row.score))
      .sort((a, b) => b.score - a.score || String(a.team_name).localeCompare(String(b.team_name)));
  }

  function getLocalSessionRows() {
    try {
      const raw = localStorage.getItem("ctf_session");
      if (!raw) return [];
      const session = JSON.parse(raw);
      if (!session || !session.team_name) return [];
      return [
        {
          team_name: String(session.team_name),
          score: Number(session.score ?? 0),
        },
      ];
    } catch (error) {
      return [];
    }
  }

  function renderRows(rows, emptyMessage) {
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!rows.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="3" class="muted-cell">${emptyMessage || "No teams on leaderboard yet."}</td>`;
      tbody.appendChild(tr);
      updateStats([]);
      setStatus("NO DATA", "status-warn");
      return;
    }

    rows.forEach((row, index) => {
      const tr = document.createElement("tr");
      if (index === 0) tr.classList.add("rank-top-1");
      if (index === 1) tr.classList.add("rank-top-2");
      if (index === 2) tr.classList.add("rank-top-3");

      const rank = index + 1;
      const rankClass = rank <= 3 ? `rank-${rank}` : "rank-n";
      const rankLabel = rank <= 3 ? ["▲", "●", "▼"][rank - 1] : `${rank}`;

      tr.innerHTML = `
        <td><span class="rank-badge ${rankClass}">${rankLabel}</span></td>
        <td class="team-name-cell">${row.team_name || "Unknown Team"}</td>
        <td class="score-cell">${row.score ?? 0}</td>
      `;
      tbody.appendChild(tr);
    });

    updateStats(rows);
    setStatus("LIVE", "status-ok");
  }

  async function fetchLeaderboardPayload() {
    if (api && typeof api.getLeaderboard === "function") {
      return api.getLeaderboard();
    }

    const response = await fetch(`${fallbackApiBase}/leaderboard`, {
      headers: {
        "Content-Type": "application/json",
      },
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok) {
      const baseMessage = payload.message || "Failed to fetch leaderboard";
      const message = payload.error ? `${baseMessage}: ${payload.error}` : baseMessage;
      throw new Error(message);
    }

    return payload;
  }

  async function loadLeaderboard() {
    try {
      const data = await fetchLeaderboardPayload();
      let rows = normalizeRows(data);
      if (!rows.length) {
        const localRows = getLocalSessionRows();
        if (localRows.length) {
          rows = localRows;
          renderRows(rows);
          setStatus("LOCAL", "status-warn");
          return;
        }
      }
      renderRows(rows);
    } catch (error) {
      const localRows = getLocalSessionRows();
      if (localRows.length) {
        renderRows(localRows);
        setStatus("LOCAL", "status-warn");
      } else {
        setStatus("OFFLINE", "status-error");
        renderRows([], "Leaderboard unavailable right now.");
      }
      showToast(error.message || "Leaderboard endpoint unavailable.", "Error");
    }
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadLeaderboard);
  }

  if (!tbody) {
    return;
  }

  try {
    loadLeaderboard();
  } catch (error) {
    setStatus("OFFLINE", "status-error");
    renderRows([], "Failed to initialize leaderboard.");
  }
})();
