(function () {
  const { byId, showToast } = window.CTFCommon;
  const api = window.CTFApi;
  const ADMIN_PASSWORD = "KGP";

  const adminRoot = byId("adminRoot");
  const adminLockScreen = byId("adminLockScreen");
  const adminPasswordInput = byId("adminPasswordInput");
  const adminPasswordSubmit = byId("adminPasswordSubmit");
  const adminPasswordError = byId("adminPasswordError");

  function showAdmin() {
    if (adminLockScreen) adminLockScreen.hidden = true;
    if (adminRoot) adminRoot.hidden = false;
  }

  function showLockScreen() {
    if (adminRoot) adminRoot.hidden = true;
    if (adminLockScreen) adminLockScreen.hidden = false;
  }

  function validatePassword() {
    const entered = (adminPasswordInput && adminPasswordInput.value) || "";
    if (entered === ADMIN_PASSWORD) {
      sessionStorage.setItem("ctf_admin_auth", "ok");
      if (adminPasswordError) adminPasswordError.hidden = true;
      showAdmin();
      initAdmin();
      return;
    }

    if (adminPasswordError) adminPasswordError.hidden = false;
    if (adminPasswordInput) {
      adminPasswordInput.focus();
      adminPasswordInput.select();
    }
  }

  const cachedAuth = sessionStorage.getItem("ctf_admin_auth") === "ok";
  if (cachedAuth) {
    showAdmin();
  } else {
    showLockScreen();
  }

  const categoryForm = byId("categoryForm");
  const challengeForm = byId("challengeForm");
  const adminCategorySelect = byId("adminCategorySelect");
  const historyCategoryFilter = byId("historyCategoryFilter");
  const challengeHistoryBody = byId("challengeHistoryBody");
  const refreshHistoryBtn = byId("refreshHistoryBtn");
  const submissionsBody = byId("submissionsBody");
  const submissionsSearch = byId("submissionsSearch");
  const submissionsResultFilter = byId("submissionsResultFilter");
  const refreshSubmissionsBtn = byId("refreshSubmissionsBtn");
  const firstBloodBody = byId("firstBloodBody");
  const refreshFirstBloodBtn = byId("refreshFirstBloodBtn");

  if (!categoryForm || !challengeForm || !adminCategorySelect || !historyCategoryFilter || !challengeHistoryBody || !refreshHistoryBtn || !submissionsBody || !submissionsSearch || !submissionsResultFilter || !refreshSubmissionsBtn || !firstBloodBody || !refreshFirstBloodBtn) {
    return;
  }

  let categories = [];
  let allSubmissions = [];

  function renderCategoryOptions() {
    adminCategorySelect.innerHTML = "";
    categories.forEach((cat) => {
      const option = document.createElement("option");
      option.value = cat.category_id;
      option.textContent = cat.category_name;
      adminCategorySelect.appendChild(option);
    });

    historyCategoryFilter.innerHTML = "";
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All categories";
    historyCategoryFilter.appendChild(allOption);

    categories.forEach((cat) => {
      const option = document.createElement("option");
      option.value = cat.category_id;
      option.textContent = cat.category_name;
      historyCategoryFilter.appendChild(option);
    });
  }

  function categoryNameById(categoryId) {
    const match = categories.find((cat) => Number(cat.category_id) === Number(categoryId));
    return match ? match.category_name : `Category ${categoryId}`;
  }

  function renderHistoryRows(challenges) {
    challengeHistoryBody.innerHTML = "";

    if (!challenges.length) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="5" class="muted-cell">No questions created yet.</td>';
      challengeHistoryBody.appendChild(row);
      return;
    }

    challenges
      .slice()
      .sort((a, b) => Number(b.challenge_no) - Number(a.challenge_no))
      .forEach((challenge) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${challenge.challenge_no}</td>
          <td>${categoryNameById(challenge.category_id)}</td>
          <td>${challenge.question_text || ""}</td>
          <td>${challenge.answer || ""}</td>
          <td>${challenge.points ?? 0}</td>
          <td><button class="btn btn-danger btn-sm" style="padding: 4px 8px; font-size: 0.75rem;" onclick="window.adminDeleteChallenge(${challenge.challenge_no})">Delete</button></td>
        `;
        challengeHistoryBody.appendChild(row);
      });
  }

  async function loadChallengeHistory() {
    const selectedCategoryId = historyCategoryFilter.value
      ? Number(historyCategoryFilter.value)
      : undefined;

    try {
      const response = await api.adminListChallenges(
        selectedCategoryId ? { category_id: selectedCategoryId } : undefined
      );
      const challenges = response.challenges || response.data || [];
      renderHistoryRows(challenges);
    } catch (error) {
      renderHistoryRows([]);
      showToast(error.message || "Failed to load previous questions.", "Error");
    }
  }

  function renderSubmissionRows(submissions) {
    submissionsBody.innerHTML = "";

    if (!submissions.length) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="6" class="muted-cell">No submissions found yet.</td>';
      submissionsBody.appendChild(row);
      return;
    }

    submissions.forEach((submission) => {
      const row = document.createElement("tr");
      const isCorrect = Number(submission.is_correct) === 1;
      
      const teamDisplay = submission.team_name ? submission.team_name : (submission.team_id ? `Team ${submission.team_id}` : "<span class='muted-cell'>[Deleted Team]</span>");
      const studentDisplay = submission.student_name ? submission.student_name : (submission.student_id ? `Student ${submission.student_id}` : "<span class='muted-cell'>[Deleted Student]</span>");

      row.innerHTML = `
        <td>#${submission.submission_id}</td>
        <td>${teamDisplay}</td>
        <td>${studentDisplay}</td>
        <td>#${submission.challenge_no}</td>
        <td>${submission.submitted_answer || ""}</td>
        <td class="${isCorrect ? "status-ok" : "status-error"}">${isCorrect ? "Correct" : "Incorrect"}</td>
      `;
      submissionsBody.appendChild(row);
    });
  }

  function applySubmissionFilters() {
    const searchText = (submissionsSearch.value || "").trim().toLowerCase();
    const resultFilter = submissionsResultFilter.value;

    const filtered = allSubmissions.filter((submission) => {
      const isCorrect = Number(submission.is_correct) === 1;
      if (resultFilter === "correct" && !isCorrect) return false;
      if (resultFilter === "incorrect" && isCorrect) return false;

      if (!searchText) return true;

      const searchable = [
        submission.submission_id,
        submission.team_name,
        submission.team_id,
        submission.student_name,
        submission.student_id,
        submission.challenge_no,
        submission.submitted_answer,
      ]
        .map((value) => String(value ?? "").toLowerCase())
        .join(" ");

      return searchable.includes(searchText);
    });

    renderSubmissionRows(filtered);
  }

  async function loadSubmissions() {
    try {
      const response = await api.adminListSubmissions();
      allSubmissions = response.submissions || response.data || [];
      applySubmissionFilters();
    } catch (error) {
      allSubmissions = [];
      renderSubmissionRows([]);
      showToast(error.message || "Failed to load submissions.", "Error");
    }
  }

  function renderFirstBloodRows(records) {
    firstBloodBody.innerHTML = "";

    if (!records.length) {
      const row = document.createElement("tr");
      row.innerHTML = '<td colspan="5" class="muted-cell">No first blood records yet.</td>';
      firstBloodBody.appendChild(row);
      return;
    }

    records.forEach((record) => {
      const row = document.createElement("tr");
      const challengeText = record.question_text
        ? `#${record.challenge_no} - ${record.question_text}`
        : `#${record.challenge_no}`;
      const awardedAt = record.awarded_at ? new Date(record.awarded_at).toLocaleString() : "-";
      
      const teamDisplay = record.team_name ? record.team_name : (record.team_id ? `Team ${record.team_id}` : "<span class='muted-cell'>[Deleted Team]</span>");
      const studentDisplay = record.student_name ? record.student_name : (record.student_id ? `Student ${record.student_id}` : "<span class='muted-cell'>[Deleted Student]</span>");

      row.innerHTML = `
        <td>${challengeText}</td>
        <td>${teamDisplay}</td>
        <td>${studentDisplay}</td>
        <td>#${record.submission_id}</td>
        <td>${awardedAt}</td>
      `;
      firstBloodBody.appendChild(row);
    });
  }

  async function loadFirstBloods() {
    try {
      const response = await api.adminListFirstBloods();
      const records = response.first_bloods || response.data || [];
      renderFirstBloodRows(records);
    } catch (error) {
      renderFirstBloodRows([]);
      showToast(error.message || "Failed to load first blood records.", "Error");
    }
  }

  async function loadCategories() {
    try {
      const response = await api.listCategories();
      categories = response.categories || response.data || [];
    } catch (error) {
      categories = [];
      showToast(error.message || "Failed to load categories.", "Error");
    }

    renderCategoryOptions();
  }

  categoryForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      category_name: byId("categoryName").value.trim(),
      description: byId("categoryDescription").value.trim(),
    };

    try {
      const created = await api.adminCreateCategory(payload);
      categories.push({ category_id: created.category_id, category_name: payload.category_name });
      renderCategoryOptions();
      await loadChallengeHistory();
      showToast("Category created.", "Success");
      categoryForm.reset();
    } catch (error) {
      showToast(error.message || "Failed to create category.", "Error");
    }
  });

  challengeForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      category_id: Number(adminCategorySelect.value),
      question_text: byId("challengeQuestion").value.trim(),
      answer: byId("challengeAnswer").value.trim(),
      points: Number(byId("challengePoints").value || 0),
    };

    try {
      await api.adminCreateChallenge(payload);
      await loadChallengeHistory();
      await loadSubmissions();
      showToast("Challenge created.", "Success");
      challengeForm.reset();
    } catch (error) {
      showToast(error.message || "Failed to create challenge.", "Error");
    }
  });

  historyCategoryFilter.addEventListener("change", loadChallengeHistory);
  refreshHistoryBtn.addEventListener("click", loadChallengeHistory);
  refreshSubmissionsBtn.addEventListener("click", loadSubmissions);
  refreshFirstBloodBtn.addEventListener("click", loadFirstBloods);
  submissionsSearch.addEventListener("input", applySubmissionFilters);
  submissionsResultFilter.addEventListener("change", applySubmissionFilters);

  if (adminPasswordSubmit) {
    adminPasswordSubmit.addEventListener("click", validatePassword);
  }

  if (adminPasswordInput) {
    adminPasswordInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        validatePassword();
      }
    });
  }

  function initAdmin() {
    loadCategories().then(async () => {
      await loadChallengeHistory();
      await loadSubmissions();
      await loadFirstBloods();
    });
  }

  window.adminDeleteChallenge = async function(challengeNo) {
    if (!confirm(`Are you sure you want to deactivate challenge #${challengeNo}?`)) return;
    try {
      await api.adminDeleteChallenge(challengeNo);
      showToast(`Challenge #${challengeNo} deactivated.`, "Success");
      await loadChallengeHistory();
    } catch (err) {
      showToast(err.message || "Failed to deactivate challenge.", "Error");
    }
  };

  if (cachedAuth) {
    initAdmin();
  }
})();
