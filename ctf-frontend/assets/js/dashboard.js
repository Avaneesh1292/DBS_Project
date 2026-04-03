(function () {
  const { byId, showToast, clearSession, requireSession, getSession, setSession, triggerHapticSuccess } = window.CTFCommon;
  const api = window.CTFApi;

  const session = requireSession("index.html");
  if (!session) return;

  const teamMeta = byId("teamMeta");
  const kpiScore = byId("kpiScore");
  const kpiChallenges = byId("kpiChallenges");
  const kpiStage = byId("kpiStage");
  const challengeGrid = byId("challengeGrid");
  const selectedTitle = byId("selectedTitle");
  const selectedQuestion = byId("selectedQuestion");
  const hintsWrap = byId("hintsWrap");
  const submitForm = byId("submitForm");
  const flagInput = byId("flagInput");

  if (!teamMeta || !kpiScore || !kpiChallenges || !kpiStage || !challengeGrid || !selectedTitle || !selectedQuestion || !hintsWrap || !submitForm || !flagInput) {
    return;
  }

  let currentChallenge = null;

  function updateHeader() {
    const fresh = getSession() || session;
    teamMeta.textContent = `${fresh.team_name} | ${fresh.student_name}`;
    kpiScore.textContent = `${fresh.score || 0}`;
    kpiStage.textContent = fresh.current_challenge_no ? `#${fresh.current_challenge_no}` : "Complete";
  }

  function renderCurrentChallengeCard() {
    challengeGrid.innerHTML = "";
    if (!currentChallenge) {
      kpiChallenges.textContent = "0";
      const message = document.createElement("p");
      message.style.color = "var(--muted)";
      message.textContent = "No active challenge. Your team may have completed all available challenge nodes.";
      challengeGrid.appendChild(message);
      return;
    }

    kpiChallenges.textContent = "1";
    const card = document.createElement("button");
    card.className = "challenge-card active";
    card.type = "button";
    card.innerHTML = `
      <div class="badge">Current #${currentChallenge.challenge_no}</div>
      <h4 style="margin: 10px 0 8px; font-family: Orbitron, sans-serif;">${currentChallenge.points} pts</h4>
      <p style="margin: 0; color: var(--muted)">${String(currentChallenge.question_text || "No challenge description available").slice(0, 90)}...</p>
    `;
    card.addEventListener("click", renderSelectedChallenge);
    challengeGrid.appendChild(card);
  }

  async function getHints(challengeNo) {
    try {
      const response = await api.listHints(challengeNo);
      return response.hints || response.data || [];
    } catch (error) {
      showToast(error.message || "Failed to load hints.", "Error");
      return [];
    }
  }

  async function renderSelectedChallenge() {
    if (!currentChallenge) {
      selectedTitle.textContent = "No active challenge";
      selectedQuestion.textContent = "Your team currently has no assigned challenge.";
      hintsWrap.innerHTML = "";
      return;
    }

    selectedTitle.textContent = `Challenge #${currentChallenge.challenge_no} (${currentChallenge.points} pts)`;
    selectedQuestion.textContent = currentChallenge.question_text;

    const hints = await getHints(currentChallenge.challenge_no);
    hintsWrap.innerHTML = "<h4 style='margin: 0 0 8px;'>Hints</h4>";

    if (!hints.length) {
      hintsWrap.innerHTML += "<p style='color: var(--muted)'>No hints available.</p>";
      return;
    }

    hints.forEach((hint) => {
      const row = document.createElement("div");
      row.className = "hint-row";
      row.innerHTML = `
        <div>
          <strong style="font-family: JetBrains Mono, monospace">Hint #${hint.hint_id}</strong>
          <div style="color: var(--muted)">${hint.hint_text || "Locked hint"}</div>
        </div>
        <button class="btn btn-secondary" type="button">Unlock (-${hint.penalty_points})</button>
      `;

      row.querySelector("button").addEventListener("click", async () => {
        try {
          const result = await api.unlockHint({ team_id: session.team_id, hint_id: hint.hint_id });
          const updated = getSession();
          updated.score = result.team_score;
          setSession(updated);
          updateHeader();
          if (result.already_unlocked) {
            showToast("Hint already unlocked.", "Info");
          } else {
            showToast(`Hint unlocked. Penalty: ${result.penalty_points}`, "Success");
          }
        } catch (error) {
          showToast(error.message || "Hint unlock failed.", "Error");
        }
      });

      hintsWrap.appendChild(row);
    });
  }

  async function loadCurrentChallengeForTeam() {
    const data = await api.listChallenges({ team_id: session.team_id });
    const current = data.challenges || data.data || [];
    currentChallenge = current.length ? current[0] : null;
    renderCurrentChallengeCard();
    await renderSelectedChallenge();
  }

  async function refreshProgressAndChallenge() {
    const progress = await api.getTeamProgress(session.team_id);
    const updated = getSession();
    updated.team_name = progress.team_name;
    updated.score = progress.score;
    updated.current_challenge_no = progress.current_challenge_no;
    setSession(updated);
    updateHeader();
    await loadCurrentChallengeForTeam();
  }

  submitForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!currentChallenge) {
      showToast("Pick a challenge first.", "Info");
      return;
    }

    const answer = flagInput.value.trim();
    if (!answer) {
      showToast("Enter a flag value.", "Info");
      return;
    }

    const payload = {
      team_id: session.team_id,
      student_id: session.student_id,
      challenge_no: currentChallenge.challenge_no,
      submitted_answer: answer,
    };

    try {
      const result = await api.submitFlag(payload);
      const correct = Boolean(result.is_correct || result.correct || false);
      if (correct) {
        const updated = getSession();
        updated.score = result.team_score;
        updated.current_challenge_no = result.current_challenge_no;
        setSession(updated);
        updateHeader();

        if (result.event_completed) {
          triggerHapticSuccess();
          showToast("Correct. Event completed for your team.", "Success");
        } else {
          triggerHapticSuccess();
          showToast("Correct. Team advanced to next challenge.", "Success");
        }

        await refreshProgressAndChallenge();
      } else {
        showToast("Wrong flag. Try again.", "Info");
      }
    } catch (error) {
      showToast(error.message || "Submission failed.", "Error");
    }

    flagInput.value = "";
  });

  const logoutBtn = byId("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      clearSession();
      window.location.href = "index.html";
    });
  }

  async function init() {
    try {
      await refreshProgressAndChallenge();
    } catch (error) {
      showToast(error.message || "Failed to initialize dashboard.", "Error");
    }
  }

  updateHeader();
  init();
})();
