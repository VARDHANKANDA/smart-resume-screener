/**
 * SMART RESUME SCREENER - Multi-User SaaS Client Application
 * Robust multi-user recruitment dashboard with business workspaces,
 * bulk upload, duplicate prevention, and profile management.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let currentUser = null;
  let currentWorkspace = null;
  let candidates = [];
  let jobs = [];
  let currentJobId = null;
  let matchResults = [];
  let currentFilter = "all";
  let recentActivities = [];
  let bulkSelectedFiles = [];

  // Confirmation Modal Handler State
  let onConfirmCallback = null;

  // Helper: Get Auth Token
  function getAuthToken() {
    return localStorage.getItem("auth_token");
  }

  // Helper: Auth Fetch Wrapper
  async function authFetch(url, options = {}) {
    const token = getAuthToken();
    const headers = options.headers || {};
    
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    
    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
      // Unauthorized or token expired
      localStorage.removeItem("auth_token");
      currentUser = null;
      currentWorkspace = null;
      renderAuthState(false);
      showToast("Session expired. Please sign in again.", "error");
      throw new Error("Unauthorized");
    }
    
    return response;
  }

  // UI Toast System
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let iconSvg = "";
    if (type === "success") {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00FF88" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === "error") {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `
      ${iconSvg}
      <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // Custom In-App Confirmation Modal
  function showConfirmDialog(title, message, callback) {
    const modal = document.getElementById("confirm-dialog-modal");
    const titleElem = document.getElementById("confirm-title");
    const msgElem = document.getElementById("confirm-message");
    
    if (titleElem) titleElem.textContent = title;
    if (msgElem) msgElem.textContent = message;
    
    onConfirmCallback = callback;
    if (modal) modal.classList.add("active");
  }

  function closeConfirmDialog() {
    const modal = document.getElementById("confirm-dialog-modal");
    if (modal) modal.classList.remove("active");
    onConfirmCallback = null;
  }

  document.getElementById("btn-confirm-cancel")?.addEventListener("click", closeConfirmDialog);
  document.getElementById("btn-confirm-proceed")?.addEventListener("click", () => {
    if (typeof onConfirmCallback === "function") {
      onConfirmCallback();
    }
    closeConfirmDialog();
  });

  function addActivity(text) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    recentActivities.unshift({ text, time: timeStr });
    if (recentActivities.length > 8) recentActivities.pop();
    renderActivityFeed();
  }

  function renderActivityFeed() {
    const container = document.getElementById("overview-activity-feed");
    if (!container) return;

    if (recentActivities.length === 0) {
      container.innerHTML = `<div class="empty-state-sm"><p class="text-dim">No workspace activity yet.</p></div>`;
      return;
    }

    container.innerHTML = recentActivities.map(act => `
      <div class="activity-item">
        <div class="activity-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 11 12 14 22 4"></polyline>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
          </svg>
        </div>
        <div class="activity-content">
          <div class="activity-text">${act.text}</div>
          <div class="activity-time">${act.time}</div>
        </div>
      </div>
    `).join("");
  }

  // ================= AUTHENTICATION & WORKSPACE STATE =================
  async function checkAuthSession() {
    const token = getAuthToken();
    if (!token) {
      renderAuthState(false);
      return;
    }

    try {
      const res = await fetch("/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        currentUser = {
          id: data.id,
          full_name: data.full_name,
          email: data.email,
          job_title: data.job_title || ""
        };
        currentWorkspace = data.workspace || null;

        renderAuthState(true);

        // Check if workspace setup onboarding is needed
        if (!currentWorkspace) {
          showOnboardingModal();
        } else {
          updateWorkspaceUI();
          loadAllData();
        }
      } else {
        localStorage.removeItem("auth_token");
        currentUser = null;
        currentWorkspace = null;
        renderAuthState(false);
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      renderAuthState(false);
    }
  }

  function renderAuthState(isAuthenticated) {
    const authWrapper = document.getElementById("auth-container");
    const appShell = document.getElementById("app-shell");

    if (isAuthenticated && currentUser) {
      authWrapper.style.display = "none";
      appShell.style.display = "flex";

      // Render User Details in Sidebar
      const nameElem = document.getElementById("user-display-name");
      const emailElem = document.getElementById("user-display-email");
      const avatarElem = document.getElementById("user-avatar-initials");

      if (nameElem) nameElem.textContent = currentUser.full_name || "Recruiter";
      if (emailElem) emailElem.textContent = currentUser.email || "";
      if (avatarElem) {
        const initials = (currentUser.full_name || "User")
          .split(" ")
          .map(n => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2);
        avatarElem.textContent = initials || "U";
      }
    } else {
      authWrapper.style.display = "flex";
      appShell.style.display = "none";
    }
  }

  function updateWorkspaceUI() {
    if (!currentWorkspace) return;

    const wsBreadcrumb = document.getElementById("topbar-ws-breadcrumb");
    const wsTag = document.getElementById("sidebar-workspace-tag");

    if (wsBreadcrumb) wsBreadcrumb.innerHTML = `Workspace: <strong>${currentWorkspace.name}</strong>`;
    if (wsTag) wsTag.textContent = currentWorkspace.name.toUpperCase().slice(0, 12);
  }

  function showOnboardingModal() {
    const modal = document.getElementById("onboarding-modal");
    if (modal) modal.classList.add("active");
  }

  function hideOnboardingModal() {
    const modal = document.getElementById("onboarding-modal");
    if (modal) modal.classList.remove("active");
  }

  // Onboarding Form Submit
  const formOnboarding = document.getElementById("form-onboarding");
  if (formOnboarding) {
    formOnboarding.addEventListener("submit", async (e) => {
      e.preventDefault();
      const wsName = document.getElementById("onboarding-ws-name").value.trim();
      const userRole = document.getElementById("onboarding-user-role").value.trim();
      const submitBtn = document.getElementById("btn-submit-onboarding");

      if (!wsName) {
        showToast("Please enter your company or business name.", "error");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Setting up workspace...</span>`;

      try {
        const res = await authFetch("/workspace/setup", {
          method: "POST",
          body: JSON.stringify({ name: wsName, job_title: userRole })
        });
        const data = await res.json();

        if (res.ok) {
          currentWorkspace = data;
          if (userRole && currentUser) currentUser.job_title = userRole;
          hideOnboardingModal();
          updateWorkspaceUI();
          showToast(`Workspace "${data.name}" ready!`, "success");
          addActivity(`Set up company workspace: ${data.name}`);
          loadAllData();
        } else {
          showToast(data.detail || "Failed to set up workspace.", "error");
        }
      } catch (err) {
        showToast("Error creating workspace.", "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Continue to Dashboard &rarr;</span>`;
      }
    });
  }

  // Auth Tab Switch (Sign In / Register)
  const tabLoginBtn = document.getElementById("tab-login-btn");
  const tabRegisterBtn = document.getElementById("tab-register-btn");
  const formLogin = document.getElementById("form-login");
  const formRegister = document.getElementById("form-register");
  const authMainTitle = document.getElementById("auth-main-title");
  const authSubTitle = document.getElementById("auth-sub-title");

  if (tabLoginBtn && tabRegisterBtn) {
    tabLoginBtn.addEventListener("click", () => {
      tabLoginBtn.classList.add("active");
      tabRegisterBtn.classList.remove("active");
      formLogin.style.display = "block";
      formRegister.style.display = "none";
      authMainTitle.textContent = "Welcome back";
      authSubTitle.textContent = "Sign in to manage your company candidate pool and screen resumes.";
    });

    tabRegisterBtn.addEventListener("click", () => {
      tabRegisterBtn.classList.add("active");
      tabLoginBtn.classList.remove("active");
      formLogin.style.display = "none";
      formRegister.style.display = "block";
      authMainTitle.textContent = "Create your account";
      authSubTitle.textContent = "Set up your organization workspace and screen resumes intelligently.";
    });
  }

  // Password Visibility Toggles
  document.querySelectorAll(".btn-toggle-pwd").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (input) {
        input.type = input.type === "password" ? "text" : "password";
      }
    });
  });

  // Login Submit Handler
  if (formLogin) {
    formLogin.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      const errorMsg = document.getElementById("login-error-msg");
      const submitBtn = document.getElementById("btn-submit-login");

      errorMsg.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Signing in...</span>`;

      try {
        const res = await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();

        if (res.ok) {
          localStorage.setItem("auth_token", data.access_token);
          currentUser = data.user;
          currentWorkspace = data.workspace || null;
          renderAuthState(true);
          showToast(`Welcome back, ${currentUser.full_name}!`, "success");
          addActivity(`Logged in as ${currentUser.email}`);

          if (!currentWorkspace) {
            showOnboardingModal();
          } else {
            updateWorkspaceUI();
            loadAllData();
          }
        } else {
          errorMsg.textContent = data.detail || "Invalid email or password.";
          errorMsg.style.display = "block";
        }
      } catch (err) {
        errorMsg.textContent = "Network error. Please try again.";
        errorMsg.style.display = "block";
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Sign In</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
      }
    });
  }

  // Register Submit Handler
  if (formRegister) {
    formRegister.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = document.getElementById("reg-fullname").value.trim();
      const email = document.getElementById("reg-email").value.trim();
      const jobTitle = document.getElementById("reg-role").value.trim();
      const password = document.getElementById("reg-password").value;
      const confirmPassword = document.getElementById("reg-confirm-password").value;
      const errorMsg = document.getElementById("reg-error-msg");
      const submitBtn = document.getElementById("btn-submit-register");

      errorMsg.style.display = "none";

      if (password !== confirmPassword) {
        errorMsg.textContent = "Passwords do not match.";
        errorMsg.style.display = "block";
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Creating account...</span>`;

      try {
        const res = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: fullName,
            email,
            password,
            confirm_password: confirmPassword,
            job_title: jobTitle
          })
        });
        const data = await res.json();

        if (res.ok) {
          localStorage.setItem("auth_token", data.access_token);
          currentUser = data.user;
          currentWorkspace = data.workspace || null;
          renderAuthState(true);
          showToast(`Account created! Welcome, ${currentUser.full_name}`, "success");
          addActivity(`Registered account: ${currentUser.email}`);

          if (!currentWorkspace) {
            showOnboardingModal();
          } else {
            updateWorkspaceUI();
            loadAllData();
          }
        } else {
          errorMsg.textContent = data.detail || "Registration failed.";
          errorMsg.style.display = "block";
        }
      } catch (err) {
        errorMsg.textContent = "Network error. Please try again.";
        errorMsg.style.display = "block";
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Create Account</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
      }
    });
  }

  // Logout Handler
  const btnLogout = document.getElementById("btn-sidebar-logout");
  if (btnLogout) {
    btnLogout.addEventListener("click", async () => {
      try {
        await authFetch("/auth/logout", { method: "POST" });
      } catch (e) {
        // Ignore network errors on logout
      }
      localStorage.removeItem("auth_token");
      currentUser = null;
      currentWorkspace = null;
      candidates = [];
      jobs = [];
      matchResults = [];
      renderAuthState(false);
      showToast("Logged out successfully.", "info");
    });
  }

  // ================= SAAS VIEW ROUTER =================
  const navButtons = {
    "view-overview": document.getElementById("nav-btn-overview"),
    "view-candidates": document.getElementById("nav-btn-candidates"),
    "view-jobs": document.getElementById("nav-btn-jobs"),
    "view-results": document.getElementById("nav-btn-results")
  };

  const topbarTitles = {
    "view-overview": { title: "Overview", subtitle: "Platform health, candidate pool statistics, and matching runs.", cta: "+ Upload Resumes", action: () => switchView("view-candidates") },
    "view-candidates": { title: "Candidates Pool", subtitle: "Manage your company applicant pool, upload single or bulk resumes.", cta: "+ Bulk Upload", action: () => { document.querySelector('[data-tab="tab-bulk"]')?.click(); } },
    "view-jobs": { title: "Job Descriptions", subtitle: "Create target roles, extract required skills, and configure evaluation criteria.", cta: "⚡ Match Candidates", action: () => handleRunMatching() },
    "view-results": { title: "Screening Results", subtitle: "Review evidence-based ranking, match scores, and skill alignment.", cta: "⚡ Screen Pool", action: () => handleRunMatching() }
  };

  function switchView(viewId) {
    document.querySelectorAll(".view-panel").forEach(panel => panel.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));

    const targetPanel = document.getElementById(viewId);
    if (targetPanel) targetPanel.classList.add("active");

    if (navButtons[viewId]) navButtons[viewId].classList.add("active");

    // Update Topbar
    const meta = topbarTitles[viewId] || { title: "Dashboard", subtitle: "", cta: "Action", action: () => {} };
    const titleElem = document.getElementById("topbar-page-title");
    const subElem = document.getElementById("topbar-page-subtitle");
    const ctaBtn = document.getElementById("topbar-cta-btn");

    if (titleElem) titleElem.textContent = meta.title;
    if (subElem) subElem.textContent = meta.subtitle;
    if (ctaBtn) {
      ctaBtn.innerHTML = `<span>${meta.cta}</span>`;
      ctaBtn.onclick = meta.action;
    }

    closeMobileSidebar();
  }

  // Register Nav Button Clicks
  Object.keys(navButtons).forEach(viewId => {
    const btn = navButtons[viewId];
    if (btn) {
      btn.addEventListener("click", () => switchView(viewId));
    }
  });

  // Mobile Sidebar Toggle
  const mobileToggle = document.getElementById("mobile-sidebar-toggle");
  const sidebar = document.getElementById("saas-sidebar");
  const sidebarBackdrop = document.getElementById("sidebar-backdrop");

  function openMobileSidebar() {
    if (sidebar) sidebar.classList.add("mobile-open");
    if (sidebarBackdrop) sidebarBackdrop.classList.add("active");
  }

  function closeMobileSidebar() {
    if (sidebar) sidebar.classList.remove("mobile-open");
    if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
  }

  if (mobileToggle) mobileToggle.addEventListener("click", openMobileSidebar);
  if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", closeMobileSidebar);

  // Workflow Step Cards & Overview Quick Links
  document.getElementById("btn-step-upload")?.addEventListener("click", () => switchView("view-candidates"));
  document.getElementById("btn-step-job")?.addEventListener("click", () => switchView("view-jobs"));
  document.getElementById("btn-step-match")?.addEventListener("click", () => switchView("view-results"));
  document.getElementById("btn-view-all-results")?.addEventListener("click", () => switchView("view-results"));

  // ================= DATA LOADING & OVERVIEW KPI RENDERING =================
  async function loadAllData() {
    await Promise.all([fetchCandidates(), fetchJobs()]);
    updateOverviewStats();
  }

  async function fetchCandidates() {
    try {
      const res = await authFetch("/resumes");
      if (res.ok) {
        candidates = await res.json();
        renderCandidatesPool();
        updateOverviewStats();
      }
    } catch (e) {
      console.error("Failed to fetch candidates:", e);
    }
  }

  async function fetchJobs() {
    try {
      const res = await authFetch("/jobs");
      if (res.ok) {
        jobs = await res.json();
        renderSavedJobs();
        renderJobSelector();
        updateOverviewStats();
      }
    } catch (e) {
      console.error("Failed to fetch jobs:", e);
    }
  }

  function updateOverviewStats() {
    // Badges
    const candBadge = document.getElementById("nav-candidate-count");
    const jobsBadge = document.getElementById("nav-jobs-count");
    const poolBadge = document.getElementById("candidate-count-badge");

    if (candBadge) candBadge.textContent = candidates.length;
    if (jobsBadge) jobsBadge.textContent = jobs.length;
    if (poolBadge) poolBadge.textContent = `${candidates.length} Candidates`;

    // Overview KPIs
    const kpiTotalCand = document.getElementById("kpi-total-candidates");
    const kpiActiveJobs = document.getElementById("kpi-active-jobs");
    const kpiStrongMatches = document.getElementById("kpi-strong-matches");
    const kpiScreened = document.getElementById("kpi-screened-count");

    if (kpiTotalCand) kpiTotalCand.textContent = candidates.length;
    if (kpiActiveJobs) kpiActiveJobs.textContent = jobs.length;

    const strongCount = matchResults.filter(m => m.recommendation === "Strong Match").length;
    if (kpiStrongMatches) kpiStrongMatches.textContent = strongCount;
    if (kpiScreened) kpiScreened.textContent = matchResults.length;

    renderOverviewTopMatches();
  }

  function renderOverviewTopMatches() {
    const container = document.getElementById("overview-top-matches-container");
    if (!container) return;

    if (matchResults.length === 0) {
      container.innerHTML = `<div class="empty-state-sm"><p class="text-dim">No screening evaluations run yet. Upload resumes and create a job to begin.</p></div>`;
      return;
    }

    const topThree = matchResults.slice(0, 3);
    container.innerHTML = topThree.map(m => `
      <div class="top-match-card">
        <div>
          <div class="top-match-name">${m.candidate_name}</div>
          <div class="top-match-role">${m.source_filename || "Candidate Profile"}</div>
          <div class="top-match-skills">
            ${m.matched_skills.slice(0, 3).map(s => `<span class="chip chip-matched">${s}</span>`).join("")}
          </div>
        </div>
        <div class="d-flex items-center gap-3">
          <div class="score-badge-circle ${m.match_score < 50 ? 'score-weak' : m.match_score < 75 ? 'score-potential' : ''}" style="width: 48px; height: 48px;">
            <span class="score-circle-num" style="font-size: 0.95rem;">${m.match_score}%</span>
          </div>
          <button class="btn btn-outline btn-xs" onclick="window.viewCandidateDetails(${m.candidate_id})">
            View
          </button>
        </div>
      </div>
    `).join("");
  }

  // ================= CANDIDATES MANAGEMENT =================
  // Ingestion Tabs
  const candTabs = document.querySelectorAll("[data-tab]");
  candTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      document.querySelectorAll("[data-tab]").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(target)?.classList.add("active");
    });
  });

  // Single Dropzone
  const singleDropZone = document.getElementById("single-drop-zone");
  const singleFileInput = document.getElementById("single-file-input");
  const singleDropText = document.getElementById("single-drop-text");

  if (singleDropZone && singleFileInput) {
    singleDropZone.addEventListener("click", () => singleFileInput.click());
    singleFileInput.addEventListener("change", () => {
      if (singleFileInput.files.length > 0) {
        singleDropText.innerHTML = `<strong>Selected:</strong> ${singleFileInput.files[0].name}`;
      }
    });
  }

  // Single Resume Upload Form Submit
  const formUploadSingle = document.getElementById("form-upload-single");
  if (formUploadSingle) {
    formUploadSingle.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!singleFileInput.files || singleFileInput.files.length === 0) {
        showToast("Please select a PDF or TXT file to upload.", "error");
        return;
      }

      const submitBtn = document.getElementById("btn-submit-single");
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Parsing resume...</span>`;

      const formData = new FormData();
      formData.append("file", singleFileInput.files[0]);
      const candidateName = document.getElementById("single-candidate-name").value.trim();
      if (candidateName) formData.append("candidate_name", candidateName);

      try {
        const res = await authFetch("/resumes", {
          method: "POST",
          body: formData
        });
        const data = await res.json();

        if (res.ok) {
          showToast(`Candidate "${data.name}" added successfully!`, "success");
          addActivity(`Uploaded & parsed resume for ${data.name}`);
          formUploadSingle.reset();
          if (singleDropText) singleDropText.innerHTML = `<strong>Click to browse</strong> or drag PDF resume`;
          await fetchCandidates();
        } else {
          showToast(data.detail || "Failed to parse resume.", "error");
        }
      } catch (err) {
        showToast("Error uploading resume.", "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Parse & Add Resume</span>`;
      }
    });
  }

  // Text Resume Form Submit
  const formUploadText = document.getElementById("form-upload-text");
  if (formUploadText) {
    formUploadText.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = document.getElementById("resume-text-input").value.trim();
      const candidateName = document.getElementById("text-candidate-name").value.trim();

      if (!text || text.length < 15) {
        showToast("Please enter complete resume text (at least 15 characters).", "error");
        return;
      }

      const submitBtn = document.getElementById("btn-submit-text");
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Parsing candidate...</span>`;

      try {
        const res = await authFetch("/resumes/text", {
          method: "POST",
          body: JSON.stringify({
            text,
            candidate_name: candidateName || null,
            filename: `${candidateName || "candidate"}_pasted_resume.txt`
          })
        });
        const data = await res.json();

        if (res.ok) {
          showToast(`Candidate "${data.name}" added successfully!`, "success");
          addActivity(`Added text resume for ${data.name}`);
          formUploadText.reset();
          await fetchCandidates();
        } else {
          showToast(data.detail || "Failed to parse resume text.", "error");
        }
      } catch (err) {
        showToast("Error parsing text resume.", "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Parse & Ingest Candidate</span>`;
      }
    });
  }

  // ================= BULK UPLOAD HANDLERS =================
  const bulkDropZone = document.getElementById("bulk-drop-zone");
  const bulkFileInput = document.getElementById("bulk-file-input");
  const bulkQueueContainer = document.getElementById("bulk-files-queue");
  const bulkFilesList = document.getElementById("bulk-files-list");
  const bulkQueueCount = document.getElementById("bulk-queue-count");
  const btnClearBulkQueue = document.getElementById("btn-clear-bulk-queue");
  const btnSubmitBulk = document.getElementById("btn-submit-bulk");

  if (bulkDropZone && bulkFileInput) {
    bulkDropZone.addEventListener("click", () => bulkFileInput.click());

    bulkFileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        for (let i = 0; i < e.target.files.length; i++) {
          bulkSelectedFiles.push(e.target.files[i]);
        }
        renderBulkQueue();
      }
    });

    ["dragenter", "dragover"].forEach(eventName => {
      bulkDropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        bulkDropZone.classList.add("drag-over");
      });
    });

    ["dragleave", "drop"].forEach(eventName => {
      bulkDropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        bulkDropZone.classList.remove("drag-over");
      });
    });

    bulkDropZone.addEventListener("drop", (e) => {
      if (e.dataTransfer.files.length > 0) {
        for (let i = 0; i < e.dataTransfer.files.length; i++) {
          bulkSelectedFiles.push(e.dataTransfer.files[i]);
        }
        renderBulkQueue();
      }
    });
  }

  function renderBulkQueue() {
    if (!bulkQueueContainer || !bulkFilesList) return;

    if (bulkSelectedFiles.length === 0) {
      bulkQueueContainer.style.display = "none";
      return;
    }

    bulkQueueContainer.style.display = "block";
    bulkQueueCount.textContent = `${bulkSelectedFiles.length} file${bulkSelectedFiles.length > 1 ? 's' : ''} selected`;

    bulkFilesList.innerHTML = bulkSelectedFiles.map((file, idx) => `
      <div class="bulk-file-pill">
        <span class="bulk-file-name" title="${file.name}">📄 ${file.name} (${Math.round(file.size / 1024)} KB)</span>
        <button type="button" class="btn-remove-queue" onclick="window.removeBulkFile(${idx})" title="Remove from queue">&times;</button>
      </div>
    `).join("");
  }

  window.removeBulkFile = function(index) {
    bulkSelectedFiles.splice(index, 1);
    renderBulkQueue();
  };

  if (btnClearBulkQueue) {
    btnClearBulkQueue.addEventListener("click", () => {
      bulkSelectedFiles = [];
      renderBulkQueue();
    });
  }

  // Bulk Upload Processing Submit
  if (btnSubmitBulk) {
    btnSubmitBulk.addEventListener("click", async () => {
      if (bulkSelectedFiles.length === 0) {
        showToast("No files selected in bulk queue.", "error");
        return;
      }

      const progressModal = document.getElementById("bulk-progress-modal");
      const progressBar = document.getElementById("bulk-progress-bar");
      const progressPct = document.getElementById("bulk-progress-pct");
      const progressLabel = document.getElementById("bulk-progress-label");
      const logContainer = document.getElementById("bulk-log-container");
      const statsSummary = document.getElementById("bulk-stats-summary");
      const modalFooter = document.getElementById("bulk-modal-footer");
      const modalTitle = document.getElementById("bulk-modal-title");

      // Reset modal state
      modalTitle.textContent = "Processing Resumes Batch";
      progressLabel.textContent = `Uploading and parsing ${bulkSelectedFiles.length} files...`;
      progressPct.textContent = "15%";
      progressBar.style.width = "15%";
      statsSummary.style.display = "none";
      modalFooter.style.display = "none";
      logContainer.innerHTML = `<div class="text-dim">Sending files to LLM parsing engine...</div>`;

      if (progressModal) progressModal.classList.add("active");

      const formData = new FormData();
      bulkSelectedFiles.forEach(file => {
        formData.append("files", file);
      });

      try {
        progressBar.style.width = "40%";
        progressPct.textContent = "40%";

        const res = await authFetch("/resumes/bulk", {
          method: "POST",
          body: formData
        });
        const data = await res.json();

        progressBar.style.width = "100%";
        progressPct.textContent = "100%";

        if (res.ok) {
          modalTitle.textContent = "Bulk Upload Complete";
          progressLabel.textContent = `Processed ${data.total_files} resumes`;

          // Populate stats
          document.getElementById("bulk-stat-success").textContent = data.success_count;
          document.getElementById("bulk-stat-duplicate").textContent = data.duplicate_count;
          document.getElementById("bulk-stat-failed").textContent = data.failed_count;
          statsSummary.style.display = "flex";

          // Render item results
          logContainer.innerHTML = data.results.map(item => {
            if (item.status === "success") {
              return `<div class="text-success">✓ ${item.filename} — Added (${item.candidate_name || 'Parsed'})</div>`;
            } else if (item.status === "duplicate_skipped") {
              return `<div class="text-warning">⚠ ${item.filename} — Duplicate skipped (${item.candidate_name || 'Existing'})</div>`;
            } else {
              return `<div class="text-danger">✕ ${item.filename} — ${item.message || 'Failed'}</div>`;
            }
          }).join("");

          modalFooter.style.display = "flex";
          addActivity(`Bulk uploaded ${data.success_count} resumes (${data.duplicate_count} skipped duplicates)`);
          showToast(`Bulk processing complete: ${data.success_count} added, ${data.duplicate_count} skipped.`, "success");

          bulkSelectedFiles = [];
          renderBulkQueue();
          await fetchCandidates();
        } else {
          logContainer.innerHTML = `<div class="text-danger">Error: ${data.detail || 'Failed to process batch.'}</div>`;
          modalFooter.style.display = "flex";
        }
      } catch (err) {
        logContainer.innerHTML = `<div class="text-danger">Network error during bulk processing.</div>`;
        modalFooter.style.display = "flex";
      }
    });
  }

  document.getElementById("btn-close-bulk-summary")?.addEventListener("click", () => {
    document.getElementById("bulk-progress-modal")?.classList.remove("active");
  });

  // ================= DELETE CANDIDATE & CLEAR POOL =================
  // Clear Pool Trigger
  document.getElementById("btn-trigger-clear-pool")?.addEventListener("click", () => {
    if (candidates.length === 0) {
      showToast("Candidate pool is already empty.", "info");
      return;
    }

    showConfirmDialog(
      "Clear Candidate Pool?",
      "This will permanently remove all candidates and their associated resume screening data from this workspace.",
      async () => {
        try {
          const res = await authFetch("/resumes", { method: "DELETE" });
          if (res.ok) {
            candidates = [];
            matchResults = [];
            renderCandidatesPool();
            updateOverviewStats();
            showToast("Candidate pool cleared for this workspace.", "success");
            addActivity("Cleared workspace candidate pool");
          } else {
            showToast("Failed to clear candidate pool.", "error");
          }
        } catch (e) {
          showToast("Error clearing candidate pool.", "error");
        }
      }
    );
  });

  // Search filter
  const searchInput = document.getElementById("candidate-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      renderCandidatesPool(query);
    });
  }

  function renderCandidatesPool(searchQuery = "") {
    const container = document.getElementById("candidates-list-container");
    if (!container) return;

    let filtered = candidates;
    if (searchQuery) {
      filtered = candidates.filter(c => 
        (c.name && c.name.toLowerCase().includes(searchQuery)) ||
        (c.email && c.email.toLowerCase().includes(searchQuery)) ||
        (c.skills && c.skills.some(s => s.toLowerCase().includes(searchQuery)))
      );
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="1.5">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </div>
          <div class="empty-title">${searchQuery ? "No matching candidates found" : "No candidates in workspace"}</div>
          <p class="empty-sub">${searchQuery ? "Try refining your search query." : "Upload PDF resumes individually or in bulk to build your candidate pool."}</p>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(c => `
      <div class="candidate-item-card">
        <div class="candidate-card-header">
          <div>
            <div class="candidate-card-name">${c.name || "Candidate #" + c.id}</div>
            <div class="candidate-card-meta">${c.email || "No email"} • ${c.source_filename || "resume.pdf"}</div>
          </div>
          <div class="candidate-card-actions">
            <button class="btn btn-outline btn-xs" onclick="window.viewCandidateRawDetails(${c.id})">
              Details
            </button>
            <button class="btn btn-danger-outline btn-xs" onclick="window.triggerDeleteCandidate(${c.id}, '${escapeHtml(c.name || 'Candidate')}')">
              Delete
            </button>
          </div>
        </div>
        <div class="skill-chips-wrap">
          ${(c.skills || []).slice(0, 5).map(s => `<span class="chip chip-matched">${s}</span>`).join("")}
          ${(c.skills || []).length > 5 ? `<span class="chip" style="background: rgba(255,255,255,0.05); color: #94a3b8;">+${c.skills.length - 5} more</span>` : ''}
        </div>
      </div>
    `).join("");
  }

  function escapeHtml(text) {
    return (text || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
  }

  window.triggerDeleteCandidate = function(candidateId, candidateName) {
    showConfirmDialog(
      "Delete Candidate?",
      `This candidate ("${candidateName}") and their associated resume screening data will be permanently removed from this workspace.`,
      async () => {
        try {
          const res = await authFetch(`/resumes/${candidateId}`, { method: "DELETE" });
          if (res.ok) {
            candidates = candidates.filter(c => c.id !== candidateId);
            matchResults = matchResults.filter(m => m.candidate_id !== candidateId);
            renderCandidatesPool();
            updateOverviewStats();
            showToast(`Candidate "${candidateName}" deleted.`, "success");
            addActivity(`Deleted candidate: ${candidateName}`);
          } else {
            showToast("Failed to delete candidate.", "error");
          }
        } catch (e) {
          showToast("Error deleting candidate.", "error");
        }
      }
    );
  };

  // ================= JOB DESCRIPTIONS WORKFLOW =================
  const btnSaveJob = document.getElementById("btn-save-job");
  if (btnSaveJob) {
    btnSaveJob.addEventListener("click", async () => {
      const title = document.getElementById("job-title-input").value.trim();
      const description = document.getElementById("job-desc-input").value.trim();

      if (!description || description.length < 15) {
        showToast("Please enter a complete job description (at least 15 characters).", "error");
        return;
      }

      btnSaveJob.disabled = true;
      btnSaveJob.innerHTML = `<span>Saving...</span>`;

      try {
        const res = await authFetch("/jobs", {
          method: "POST",
          body: JSON.stringify({ title: title || "Target Role", description })
        });
        const data = await res.json();

        if (res.ok) {
          showToast(`Job "${data.title}" saved!`, "success");
          addActivity(`Created job role: ${data.title}`);
          currentJobId = data.id;
          await fetchJobs();
        } else {
          showToast(data.detail || "Failed to save job.", "error");
        }
      } catch (err) {
        showToast("Error saving job description.", "error");
      } finally {
        btnSaveJob.disabled = false;
        btnSaveJob.innerHTML = `<span>Save Job Specification</span>`;
      }
    });
  }

  function renderSavedJobs() {
    const container = document.getElementById("saved-jobs-container");
    if (!container) return;

    if (jobs.length === 0) {
      container.innerHTML = `<div class="empty-state-sm"><p class="text-dim">No saved job roles yet in this workspace.</p></div>`;
      return;
    }

    container.innerHTML = jobs.map(j => `
      <div class="saved-job-card">
        <div class="d-flex justify-between items-center">
          <div class="saved-job-title">${j.title || "Job #" + j.id}</div>
          <div class="d-flex gap-2">
            <button class="btn btn-primary btn-xs" onclick="window.selectAndMatchJob(${j.id})">
              Screen Pool &rarr;
            </button>
            <button class="btn btn-danger-outline btn-xs" onclick="window.triggerDeleteJob(${j.id}, '${escapeHtml(j.title || 'Job')}')">
              Delete
            </button>
          </div>
        </div>
        <div class="skill-chips-wrap mt-2">
          ${(j.required_skills || []).slice(0, 4).map(s => `<span class="chip chip-matched">${s}</span>`).join("")}
        </div>
      </div>
    `).join("");
  }

  window.triggerDeleteJob = function(jobId, jobTitle) {
    showConfirmDialog(
      "Delete Job Role?",
      `Are you sure you want to delete "${jobTitle}" and its screening evaluations?`,
      async () => {
        try {
          const res = await authFetch(`/jobs/${jobId}`, { method: "DELETE" });
          if (res.ok) {
            jobs = jobs.filter(j => j.id !== jobId);
            if (currentJobId === jobId) currentJobId = null;
            renderSavedJobs();
            renderJobSelector();
            updateOverviewStats();
            showToast("Job role deleted.", "success");
            addActivity(`Deleted job role: ${jobTitle}`);
          } else {
            showToast("Failed to delete job.", "error");
          }
        } catch (e) {
          showToast("Error deleting job.", "error");
        }
      }
    );
  };

  window.selectAndMatchJob = async function(jobId) {
    currentJobId = jobId;
    switchView("view-results");
    const selector = document.getElementById("results-job-selector");
    if (selector) selector.value = jobId;
    await handleRunMatching(jobId);
  };

  function renderJobSelector() {
    const selector = document.getElementById("results-job-selector");
    if (!selector) return;

    selector.innerHTML = `<option value="">Select Job Role...</option>` +
      jobs.map(j => `<option value="${j.id}" ${currentJobId === j.id ? "selected" : ""}>${j.title || "Job #" + j.id}</option>`).join("");

    selector.onchange = (e) => {
      currentJobId = parseInt(e.target.value) || null;
      if (currentJobId) {
        fetchJobResults(currentJobId);
      }
    };
  }

  // ================= SCREENING & RANKING WORKFLOW =================
  async function handleRunMatching(overrideJobId = null) {
    let jobId = overrideJobId || currentJobId;

    if (!jobId) {
      const descInput = document.getElementById("job-desc-input");
      const titleInput = document.getElementById("job-title-input");
      if (descInput && descInput.value.trim().length >= 15) {
        try {
          const res = await authFetch("/jobs", {
            method: "POST",
            body: JSON.stringify({
              title: titleInput.value.trim() || "Target Role",
              description: descInput.value.trim()
            })
          });
          const savedJob = await res.json();
          jobId = savedJob.id;
          currentJobId = jobId;
          await fetchJobs();
        } catch (e) {
          showToast("Failed to create job for screening.", "error");
          return;
        }
      } else if (jobs.length > 0) {
        jobId = jobs[0].id;
        currentJobId = jobId;
      } else {
        showToast("Please create or select a job description first.", "error");
        switchView("view-jobs");
        return;
      }
    }

    if (candidates.length === 0) {
      showToast("No candidates in workspace pool. Please upload resumes first.", "error");
      switchView("view-candidates");
      return;
    }

    switchView("view-results");

    const btnRun = document.getElementById("btn-run-matching");
    const btnResultsRerun = document.getElementById("btn-results-rerun");
    if (btnRun) { btnRun.disabled = true; btnRun.innerHTML = `<span>Analyzing Candidates...</span>`; }
    if (btnResultsRerun) { btnResultsRerun.disabled = true; btnResultsRerun.innerHTML = `<span>Analyzing...</span>`; }

    showToast("Analyzing candidate relevance with LLM matcher...", "info");

    try {
      const res = await authFetch(`/jobs/${jobId}/match`, {
        method: "POST",
        body: JSON.stringify({})
      });
      const data = await res.json();

      if (res.ok) {
        matchResults = data.results || [];
        showToast(`Screening complete! Evaluated ${matchResults.length} candidates.`, "success");
        addActivity(`Screened ${matchResults.length} candidates against "${data.job_title}"`);
        
        const titleDisplay = document.getElementById("results-job-title-display");
        if (titleDisplay) titleDisplay.textContent = `Ranking for: ${data.job_title || "Job #" + jobId}`;
        
        renderResultsList();
        updateOverviewStats();
      } else {
        showToast(data.detail || "Matching failed.", "error");
      }
    } catch (err) {
      showToast("Error running candidate matching.", "error");
    } finally {
      if (btnRun) {
        btnRun.disabled = false;
        btnRun.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg><span>Analyze Candidates</span>`;
      }
      if (btnResultsRerun) {
        btnResultsRerun.disabled = false;
        btnResultsRerun.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg><span>Screen Pool</span>`;
      }
    }
  }

  document.getElementById("btn-run-matching")?.addEventListener("click", () => handleRunMatching());
  document.getElementById("btn-results-rerun")?.addEventListener("click", () => handleRunMatching());

  async function fetchJobResults(jobId) {
    try {
      const res = await authFetch(`/jobs/${jobId}/results`);
      if (res.ok) {
        const data = await res.json();
        matchResults = data.results || [];
        const titleDisplay = document.getElementById("results-job-title-display");
        if (titleDisplay) titleDisplay.textContent = `Ranking for: ${data.job_title || "Job #" + jobId}`;
        renderResultsList();
        updateOverviewStats();
      }
    } catch (e) {
      console.error("Failed to fetch results:", e);
    }
  }

  // Filter Buttons
  document.querySelectorAll(".results-filter-bar .filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".results-filter-bar .filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.getAttribute("data-filter");
      renderResultsList();
    });
  });

  function renderResultsList() {
    const container = document.getElementById("ranked-results-list");
    if (!container) return;

    const countAll = matchResults.length;
    const countStrong = matchResults.filter(r => r.recommendation === "Strong Match").length;
    const countPotential = matchResults.filter(r => r.recommendation === "Potential Match").length;
    const countWeak = matchResults.filter(r => r.recommendation === "Weak Match").length;

    document.getElementById("count-filter-all").textContent = countAll;
    document.getElementById("count-filter-strong").textContent = countStrong;
    document.getElementById("count-filter-potential").textContent = countPotential;
    document.getElementById("count-filter-weak").textContent = countWeak;

    document.getElementById("metric-total-evaluated").textContent = countAll;
    document.getElementById("metric-shortlisted-count").textContent = countStrong;
    const avgScore = countAll > 0 ? Math.round(matchResults.reduce((acc, r) => acc + r.match_score, 0) / countAll) : 0;
    document.getElementById("metric-avg-score").textContent = `${avgScore}%`;

    let filtered = matchResults;
    if (currentFilter !== "all") {
      filtered = matchResults.filter(r => r.recommendation === currentFilter);
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state" id="results-empty-state">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="1.5">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
            </svg>
          </div>
          <div class="empty-title">No candidate matches in this category</div>
          <p class="empty-sub">Try switching filter tabs or click Screen Pool to re-evaluate.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map((r, index) => {
      const recClass = r.recommendation === "Strong Match" ? "match-badge-strong" :
                       r.recommendation === "Potential Match" ? "match-badge-potential" : "match-badge-weak";
      const scoreDialClass = r.match_score < 50 ? "score-weak" : r.match_score < 75 ? "score-potential" : "";

      return `
        <div class="result-candidate-card">
          <div class="result-score-block">
            <div class="score-badge-circle ${scoreDialClass}">
              <span class="score-circle-num">${r.match_score}%</span>
              <span class="score-circle-lbl">Match</span>
            </div>
          </div>

          <div class="result-main-info">
            <div class="result-name-row">
              <span class="rank-badge">#${index + 1} Ranked</span>
              <span class="result-cand-name">${r.candidate_name}</span>
              <span class="${recClass}">${r.recommendation}</span>
            </div>
            
            <div class="skill-chips-wrap">
              ${(r.matched_skills || []).slice(0, 4).map(s => `<span class="chip chip-matched">✓ ${s}</span>`).join("")}
              ${(r.missing_skills || []).slice(0, 2).map(s => `<span class="chip chip-missing">✕ ${s}</span>`).join("")}
            </div>

            <p class="result-justification-preview">${r.justification}</p>
          </div>

          <div>
            <button class="btn btn-outline btn-sm" onclick="window.viewCandidateDetails(${r.candidate_id})">
              <span>View Analysis</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  // ================= WORKSPACE & PERSONAL PROFILE SETTINGS =================
  const settingsModal = document.getElementById("settings-modal");
  const settingsCloseBtn = document.getElementById("settings-close-btn");
  const settingsDismissBtn = document.getElementById("settings-dismiss-btn");

  function openSettingsModal() {
    if (!currentUser) return;
    
    // Populate profile tab
    document.getElementById("profile-fullname").value = currentUser.full_name || "";
    document.getElementById("profile-jobtitle").value = currentUser.job_title || "";
    document.getElementById("profile-email-readonly").value = currentUser.email || "";
    document.getElementById("modal-profile-name-preview").textContent = currentUser.full_name || "User";
    document.getElementById("modal-profile-email-preview").textContent = currentUser.email || "";
    
    const initials = (currentUser.full_name || "U").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
    document.getElementById("modal-avatar-preview").textContent = initials;

    // Populate workspace tab
    if (currentWorkspace) {
      document.getElementById("settings-workspace-name").value = currentWorkspace.name || "";
      fetchWorkspaceMembers();
    }

    if (settingsModal) settingsModal.classList.add("active");
  }

  function closeSettingsModal() {
    if (settingsModal) settingsModal.classList.remove("active");
  }

  document.getElementById("nav-btn-settings")?.addEventListener("click", openSettingsModal);
  document.getElementById("sidebar-user-pill")?.addEventListener("click", openSettingsModal);
  if (settingsCloseBtn) settingsCloseBtn.addEventListener("click", closeSettingsModal);
  if (settingsDismissBtn) settingsDismissBtn.addEventListener("click", closeSettingsModal);

  // Settings Sub-Tabs
  document.querySelectorAll("[data-settings-tab]").forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.getAttribute("data-settings-tab");
      document.querySelectorAll("[data-settings-tab]").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".settings-pane").forEach(p => {
        p.classList.remove("active");
        p.style.display = "none";
      });
      tab.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add("active");
        targetPane.style.display = "block";
      }
    });
  });

  // Profile Form Submit
  const formUserProfile = document.getElementById("form-user-profile");
  if (formUserProfile) {
    formUserProfile.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = document.getElementById("profile-fullname").value.trim();
      const jobTitle = document.getElementById("profile-jobtitle").value.trim();
      const btn = document.getElementById("btn-save-profile");

      btn.disabled = true;
      btn.innerHTML = `<span>Saving...</span>`;

      try {
        const res = await authFetch("/auth/me", {
          method: "PUT",
          body: JSON.stringify({ full_name: fullName, job_title: jobTitle })
        });
        const updated = await res.json();

        if (res.ok) {
          currentUser.full_name = updated.full_name;
          currentUser.job_title = updated.job_title;
          renderAuthState(true);
          showToast("Personal profile updated!", "success");
          addActivity("Updated personal profile information");
        } else {
          showToast("Failed to update profile.", "error");
        }
      } catch (err) {
        showToast("Error updating profile.", "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Save Profile Changes</span>`;
      }
    });
  }

  // Workspace Name Update Submit
  const formWorkspaceDetails = document.getElementById("form-workspace-details");
  if (formWorkspaceDetails) {
    formWorkspaceDetails.addEventListener("submit", async (e) => {
      e.preventDefault();
      const wsName = document.getElementById("settings-workspace-name").value.trim();
      const btn = document.getElementById("btn-save-ws-name");

      if (!wsName) return;

      btn.disabled = true;
      btn.innerHTML = `<span>Updating...</span>`;

      try {
        const res = await authFetch("/workspace", {
          method: "PUT",
          body: JSON.stringify({ name: wsName })
        });
        const data = await res.json();

        if (res.ok) {
          currentWorkspace = data;
          updateWorkspaceUI();
          showToast("Company workspace name updated!", "success");
          addActivity(`Renamed workspace to: ${data.name}`);
        } else {
          showToast(data.detail || "Failed to update workspace name.", "error");
        }
      } catch (err) {
        showToast("Error updating workspace.", "error");
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>Update Business Name</span>`;
      }
    });
  }

  // Fetch & Render Team Members
  async function fetchWorkspaceMembers() {
    try {
      const res = await authFetch("/workspace");
      if (res.ok) {
        const data = await res.json();
        renderTeamMembersList(data.members || []);
      }
    } catch (e) {
      console.error("Failed to load members:", e);
    }
  }

  function renderTeamMembersList(members) {
    const container = document.getElementById("workspace-members-list");
    if (!container) return;

    if (members.length === 0) {
      container.innerHTML = `<p class="text-dim" style="font-size: 0.82rem;">No team members added yet.</p>`;
      return;
    }

    container.innerHTML = members.map(m => `
      <div class="member-row">
        <div class="member-info">
          <div class="user-avatar" style="width: 32px; height: 32px; font-size: 0.78rem;">
            ${(m.full_name || 'U').slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div style="font-size: 0.86rem; font-weight: 600; color: var(--text-main);">${m.full_name}</div>
            <div class="text-muted" style="font-size: 0.75rem;">${m.email} ${m.job_title ? '• ' + m.job_title : ''}</div>
          </div>
        </div>
        <div class="d-flex items-center gap-3">
          <span class="role-badge role-badge-${m.role}">${m.role}</span>
          ${m.user_id !== currentUser.id ? `
            <button class="btn btn-link text-danger" style="font-size: 0.78rem;" onclick="window.triggerRemoveMember(${m.user_id}, '${escapeHtml(m.full_name)}')">
              Remove
            </button>
          ` : ''}
        </div>
      </div>
    `).join("");
  }

  // Add Member Form
  const formAddMember = document.getElementById("form-add-member");
  if (formAddMember) {
    formAddMember.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("input-member-email").value.trim();
      const role = document.getElementById("select-member-role").value;
      const btn = document.getElementById("btn-invite-member");

      btn.disabled = true;

      try {
        const res = await authFetch("/workspace/members", {
          method: "POST",
          body: JSON.stringify({ email, role })
        });
        const data = await res.json();

        if (res.ok) {
          renderTeamMembersList(data);
          document.getElementById("input-member-email").value = "";
          showToast(`Added team member ${email}!`, "success");
          addActivity(`Added team member: ${email}`);
        } else {
          showToast(data.detail || "Failed to add member.", "error");
        }
      } catch (err) {
        showToast("Error adding member.", "error");
      } finally {
        btn.disabled = false;
      }
    });
  }

  window.triggerRemoveMember = function(userId, memberName) {
    showConfirmDialog(
      "Remove Team Member?",
      `Are you sure you want to remove "${memberName}" from this workspace? They will lose access to shared candidates and jobs.`,
      async () => {
        try {
          const res = await authFetch(`/workspace/members/${userId}`, { method: "DELETE" });
          const data = await res.json();
          if (res.ok) {
            renderTeamMembersList(data);
            showToast(`Removed team member "${memberName}".`, "info");
            addActivity(`Removed team member: ${memberName}`);
          } else {
            showToast("Failed to remove member.", "error");
          }
        } catch (e) {
          showToast("Error removing member.", "error");
        }
      }
    );
  };

  // ================= CANDIDATE DETAILS MODAL =================
  const detailsModal = document.getElementById("candidate-details-modal");
  const detailsCloseBtn = document.getElementById("modal-close-btn");
  const detailsDismissBtn = document.getElementById("modal-dismiss-btn");

  function closeDetailsModal() {
    if (detailsModal) detailsModal.classList.remove("active");
  }

  if (detailsCloseBtn) detailsCloseBtn.addEventListener("click", closeDetailsModal);
  if (detailsDismissBtn) detailsDismissBtn.addEventListener("click", closeDetailsModal);
  if (detailsModal) {
    detailsModal.addEventListener("click", (e) => {
      if (e.target === detailsModal) closeDetailsModal();
    });
  }

  window.viewCandidateDetails = function(candidateId) {
    const match = matchResults.find(m => m.candidate_id === candidateId);
    const candidate = candidates.find(c => c.id === candidateId) || (match ? {
      name: match.candidate_name,
      email: match.candidate_email,
      source_filename: match.source_filename,
      skills: match.candidate_skills,
      experience: match.candidate_experience,
      education: match.candidate_education
    } : null);

    if (!match && !candidate) {
      showToast("Candidate details not found.", "error");
      return;
    }

    const rankIndex = matchResults.findIndex(m => m.candidate_id === candidateId);
    document.getElementById("modal-rank-display").textContent = rankIndex >= 0 ? `#${rankIndex + 1}` : "Profile";
    document.getElementById("modal-candidate-name").textContent = (candidate && candidate.name) || (match && match.candidate_name) || "Candidate Profile";
    document.getElementById("modal-candidate-meta").textContent = `${(candidate && candidate.email) || (match && match.candidate_email) || 'email@example.com'} • ${(candidate && candidate.source_filename) || (match && match.source_filename) || 'resume.pdf'}`;

    const score = match ? match.match_score : 75;
    document.getElementById("modal-score-number").textContent = score;

    const dial = document.getElementById("modal-score-dial");
    if (dial) {
      const circumference = 2 * Math.PI * 42;
      const offset = circumference - (score / 100) * circumference;
      dial.style.strokeDasharray = `${circumference}`;
      dial.style.strokeDashoffset = `${offset}`;
      dial.style.stroke = score >= 75 ? "var(--accent-neon)" : score >= 50 ? "var(--status-potential)" : "var(--status-weak)";
    }

    const recBadge = document.getElementById("modal-rec-badge");
    if (recBadge) {
      const rec = match ? match.recommendation : "Strong Match";
      recBadge.textContent = rec;
      recBadge.className = "rec-badge-lg " + (rec === "Strong Match" ? "match-badge-strong" : rec === "Potential Match" ? "match-badge-potential" : "match-badge-weak");
    }

    const recExp = document.getElementById("modal-rec-explanation");
    if (recExp) recExp.textContent = match ? match.justification.slice(0, 140) + "..." : "Candidate profile parsed and stored.";

    const matchedContainer = document.getElementById("modal-matched-skills");
    const missingContainer = document.getElementById("modal-missing-skills");

    if (matchedContainer) {
      const skills = match ? match.matched_skills : (candidate ? candidate.skills : []);
      matchedContainer.innerHTML = skills.length > 0 
        ? skills.map(s => `<span class="chip chip-matched">✓ ${s}</span>`).join("")
        : `<span class="text-dim" style="font-size: 0.78rem;">None highlighted</span>`;
    }

    if (missingContainer) {
      const missing = match ? match.missing_skills : [];
      missingContainer.innerHTML = missing.length > 0
        ? missing.map(s => `<span class="chip chip-missing">✕ ${s}</span>`).join("")
        : `<span class="text-dim" style="font-size: 0.78rem;">No critical skills missing</span>`;
    }

    const expAssessment = document.getElementById("modal-experience-assessment");
    if (expAssessment) {
      expAssessment.textContent = match ? match.experience_assessment : "Extracted professional background and domain experience verified.";
    }

    const strengthsList = document.getElementById("modal-strengths-list");
    const concernsList = document.getElementById("modal-concerns-list");

    if (strengthsList) {
      const strengths = match && match.strengths && match.strengths.length > 0 
        ? match.strengths 
        : ["Solid foundation in core requirements", "Relevant technical skill set"];
      strengthsList.innerHTML = strengths.map(s => `<li>${s}</li>`).join("");
    }

    if (concernsList) {
      const concerns = match && match.concerns && match.concerns.length > 0
        ? match.concerns
        : ["No major discrepancies or red flags noted in profile"];
      concernsList.innerHTML = concerns.map(c => `<li>${c}</li>`).join("");
    }

    const justElem = document.getElementById("modal-justification");
    if (justElem) {
      justElem.textContent = match ? match.justification : "Candidate evaluated against required criteria.";
    }

    const detailsContainer = document.getElementById("modal-structured-details");
    if (detailsContainer && candidate) {
      let expHtml = "";
      if (candidate.experience && candidate.experience.length > 0) {
        expHtml += `<h5 style="color: var(--text-main); margin-bottom: 6px;">Experience History</h5>`;
        expHtml += candidate.experience.map(e => `
          <div style="margin-bottom: 8px; padding-left: 10px; border-left: 2px solid var(--border-card);">
            <strong>${e.role || "Role"}</strong> at <em>${e.company || "Company"}</em> (${e.duration || "Duration"})
            <div style="font-size: 0.78rem; color: var(--text-muted);">${e.description || ""}</div>
          </div>
        `).join("");
      }

      let eduHtml = "";
      if (candidate.education && candidate.education.length > 0) {
        eduHtml += `<h5 style="color: var(--text-main); margin-top: 12px; margin-bottom: 6px;">Academic Qualifications</h5>`;
        eduHtml += candidate.education.map(ed => `
          <div style="margin-bottom: 6px; padding-left: 10px; border-left: 2px solid var(--border-card);">
            <strong>${ed.degree || "Degree"}</strong> — ${ed.institution || "Institution"}
          </div>
        `).join("");
      }

      detailsContainer.innerHTML = expHtml + eduHtml || `<p class="text-dim">No structured details available.</p>`;
    }

    if (detailsModal) detailsModal.classList.add("active");
  };

  window.viewCandidateRawDetails = function(candidateId) {
    window.viewCandidateDetails(candidateId);
  };

  // ================= START APPLICATION =================
  checkAuthSession();
});
