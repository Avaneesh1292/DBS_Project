(function () {
  const { byId, showToast, setSession } = window.CTFCommon;
  const api = window.CTFApi;

  const registerForm = byId("registerForm");
  const loginForm = byId("loginForm");

  if (!registerForm || !loginForm) {
    return;
  }

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const nameInput = byId("regName");
    const emailInput = byId("regEmail");
    const teamInput = byId("regTeam");
    if (!nameInput || !emailInput || !teamInput) {
      showToast("Registration form is incomplete.", "Error");
      return;
    }

    const input = {
      name: nameInput.value.trim(),
      email: emailInput.value.trim(),
      team_name: teamInput.value.trim(),
    };

    try {
      const data = await api.registerStudent(input);
      const session = {
        student_id: data.student_id,
        student_name: data.name || input.name,
        email: data.email || input.email,
        team_id: data.team_id,
        team_name: data.team_name || input.team_name,
        score: data.score || 0,
        current_challenge_no: data.current_challenge_no || null,
      };
      setSession(session);
      showToast("Registration successful. Redirecting...", "Success");
      window.location.href = "dashboard.html";
    } catch (error) {
      showToast(error.message || "Registration failed.", "Error");
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const loginInput = byId("loginEmail");
    if (!loginInput) {
      showToast("Login form is incomplete.", "Error");
      return;
    }

    const input = {
      email: loginInput.value.trim(),
    };

    try {
      const data = await api.loginStudent(input);
      const session = {
        student_id: data.student_id,
        student_name: data.name,
        email: data.email,
        team_id: data.team_id,
        team_name: data.team_name,
        score: data.score || 0,
        current_challenge_no: data.current_challenge_no || null,
      };
      setSession(session);
      showToast("Login successful.", "Success");
      window.location.href = "dashboard.html";
    } catch (error) {
      showToast(error.message || "Login failed.", "Error");
    }
  });

  api.health().catch(() => {
    showToast("Backend seems offline. Start app.py before login/register.", "Info");
  });
})();
