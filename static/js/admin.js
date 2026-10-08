/**
 * Admin Dashboard Controller
 * Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
 * Author: Saitharun Cherukuri
 * Enforces role-based management: user directory, biometric enrollment, settings & metrics.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Elements - Metrics
    const metricTotalUsers = document.getElementById("metric-total-users");
    const metricActiveUsers = document.getElementById("metric-active-users");
    const metricScansToday = document.getElementById("metric-scans-today");
    const metricVerifiedRatio = document.getElementById("metric-verified-ratio");
    const metricAvgAccuracy = document.getElementById("metric-avg-accuracy");

    // Elements - User Table & Filters
    const usersTableBody = document.getElementById("users-table-body");
    const userSearchInput = document.getElementById("user-search-input");
    const userDeptFilter = document.getElementById("user-dept-filter");
    const btnRefreshUsers = document.getElementById("btn-refresh-users");

    // Elements - Modals
    const modalEnroll = document.getElementById("modal-enroll-user");
    const btnOpenRegister = document.getElementById("btn-open-register");
    const btnCloseEnroll = document.getElementById("btn-close-enroll");
    const btnCancelEnroll = document.getElementById("btn-cancel-enroll");
    const formEnroll = document.getElementById("form-enroll-user");

    const modalEdit = document.getElementById("modal-edit-user");
    const btnCloseEdit = document.getElementById("btn-close-edit");
    const btnCancelEdit = document.getElementById("btn-cancel-edit");
    const formEdit = document.getElementById("form-edit-user");

    const modalSettings = document.getElementById("modal-settings");
    const btnOpenSettings = document.getElementById("btn-open-settings");
    const btnCloseSettings = document.getElementById("btn-close-settings");

    // Enrollment Webcam & File Tabs
    const tabBtnWebcam = document.getElementById("tab-btn-webcam");
    const tabBtnUpload = document.getElementById("tab-btn-upload");
    const enrollWebcamPane = document.getElementById("enroll-webcam-pane");
    const enrollUploadPane = document.getElementById("enroll-upload-pane");
    const enrollVideo = document.getElementById("enroll-video");
    const enrollCanvas = document.getElementById("enroll-canvas");
    const btnSnapEnroll = document.getElementById("btn-snap-enroll");
    const enrollFileInput = document.getElementById("enroll-file-input");
    const enrollPreviewBox = document.getElementById("enroll-preview-box");
    const enrollPreviewImg = document.getElementById("enroll-preview-img");
    const btnRetakeEnroll = document.getElementById("btn-retake-enroll");
    const enrollErrorAlert = document.getElementById("enroll-error-alert");
    const enrollErrorMsg = document.getElementById("enroll-error-msg");
    const btnSubmitEnroll = document.getElementById("btn-submit-enroll");

    // Settings elements
    const thresholdSlider = document.getElementById("threshold-slider");
    const sliderThresholdVal = document.getElementById("slider-threshold-val");
    const btnSaveThreshold = document.getElementById("btn-save-threshold");
    const formChangePwd = document.getElementById("form-change-pwd");
    const pwdChangeMsg = document.getElementById("pwd-change-msg");

    // State
    let enrollStream = null;
    let capturedFaceBase64 = null;
    let selectedFaceFile = null;

    // Auth helper
    function getAuthHeaders(extra = {}) {
        const token = localStorage.getItem("faceid_admin_token");
        const headers = { ...extra };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
    }

    // 1. Fetch & Display Overview Stats
    async function loadStats() {
        try {
            const resp = await fetch("/api/admin/stats", {
                headers: getAuthHeaders()
            });
            if (!resp.ok) return;
            const data = await resp.json();
            metricTotalUsers.textContent = data.total_users;
            metricActiveUsers.textContent = data.active_users;
            metricScansToday.textContent = data.scans_today;
            metricVerifiedRatio.textContent = `${data.verified_today} verified`;
            metricAvgAccuracy.textContent = `${data.avg_accuracy_today.toFixed(1)}%`;
        } catch (e) {
            console.error("Stats load failed", e);
        }
    }

    // 2. Fetch & Display Users
    async function loadUsers() {
        const search = userSearchInput.value.trim();
        const dept = userDeptFilter.value;
        const params = new URLSearchParams();
        if (search) params.append("search", search);
        if (dept) params.append("department", dept);

        try {
            const resp = await fetch(`/api/admin/users?${params.toString()}`, {
                headers: getAuthHeaders()
            });
            if (!resp.ok) {
                if (resp.status === 401) {
                    window.location.href = "/admin/login";
                    return;
                }
                throw new Error("Failed to load users");
            }

            const users = await resp.json();
            if (users.length === 0) {
                usersTableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="py-12 text-center text-slate-500">
                            <i class="fa-solid fa-users-slash text-2xl text-slate-600 mb-2"></i>
                            <p>No registered users found.</p>
                            <p class="text-[10px] text-slate-600 mt-1">Click "Enroll New User" to register someone's face.</p>
                        </td>
                    </tr>
                `;
                return;
            }

            usersTableBody.innerHTML = users.map(u => {
                const statusBadge = u.is_active
                    ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-950 border border-emerald-700 text-emerald-400">ACTIVE</span>'
                    : '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-slate-800 border border-slate-700 text-slate-400">INACTIVE</span>';

                const avatar = u.photo_path
                    ? `<img src="${u.photo_path}" class="w-9 h-9 object-cover rounded-xl border border-slate-700 shadow-sm">`
                    : `<div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-400">${u.full_name[0]}</div>`;

                return `
                    <tr class="hover:bg-slate-900/40 transition-colors">
                        <td class="py-3 px-4">
                            <div class="flex items-center space-x-3">
                                ${avatar}
                                <div>
                                    <span class="font-bold text-white block">${u.full_name}</span>
                                    <span class="text-[10px] text-slate-400">${u.notes || ''}</span>
                                </div>
                            </div>
                        </td>
                        <td class="py-3 px-4 font-mono font-semibold text-cyan-300">${u.user_id}</td>
                        <td class="py-3 px-4">
                            <span class="block text-slate-200">${u.department || 'N/A'}</span>
                            <span class="text-[10px] text-slate-500">${u.role_title || 'General'}</span>
                        </td>
                        <td class="py-3 px-4 font-mono text-[11px] text-slate-400">
                            <div>${u.email || '-'}</div>
                            <div class="text-[10px] text-slate-500">${u.phone || ''}</div>
                        </td>
                        <td class="py-3 px-4">${statusBadge}</td>
                        <td class="py-3 px-4 font-mono text-slate-500 text-[11px]">${u.created_at || 'N/A'}</td>
                        <td class="py-3 px-4 text-right space-x-2">
                            <button onclick="openEditModal('${u.user_id}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors" title="Edit">
                                <i class="fa-solid fa-pen-to-square"></i>
                            </button>
                            <button onclick="deleteUser('${u.user_id}', '${u.full_name}')" class="px-2.5 py-1 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 hover:text-white transition-colors" title="Delete">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');

        } catch (e) {
            usersTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="py-8 text-center text-rose-400">
                        Error loading users: ${e.message}
                    </td>
                </tr>
            `;
        }
    }

    // 3. User Enrollment Webcam Controls
    async function startEnrollCamera() {
        try {
            enrollStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 400, height: 400, facingMode: "user" }
            });
            enrollVideo.srcObject = enrollStream;
            await enrollVideo.play();
        } catch (err) {
            console.warn("Enrollment webcam failed:", err);
            // Default to upload tab if camera fails
            switchToUploadTab();
        }
    }

    function stopEnrollCamera() {
        if (enrollStream) {
            enrollStream.getTracks().forEach(t => t.stop());
            enrollStream = null;
        }
    }

    function switchToWebcamTab() {
        tabBtnWebcam.className = "px-2.5 py-1 rounded-md text-[11px] font-semibold bg-cyan-600 text-white transition-all";
        tabBtnUpload.className = "px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:text-white transition-all";
        enrollWebcamPane.classList.remove("hidden");
        enrollUploadPane.classList.add("hidden");
        startEnrollCamera();
    }

    function switchToUploadTab() {
        tabBtnUpload.className = "px-2.5 py-1 rounded-md text-[11px] font-semibold bg-cyan-600 text-white transition-all";
        tabBtnWebcam.className = "px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:text-white transition-all";
        enrollUploadPane.classList.remove("hidden");
        enrollWebcamPane.classList.add("hidden");
        stopEnrollCamera();
    }

    tabBtnWebcam.addEventListener("click", switchToWebcamTab);
    tabBtnUpload.addEventListener("click", switchToUploadTab);

    // Snap face from enroll video
    btnSnapEnroll.addEventListener("click", () => {
        if (!enrollVideo.videoWidth) return;
        enrollCanvas.width = enrollVideo.videoWidth;
        enrollCanvas.height = enrollVideo.videoHeight;
        const ctx = enrollCanvas.getContext("2d");
        ctx.translate(enrollCanvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(enrollVideo, 0, 0, enrollCanvas.width, enrollCanvas.height);

        capturedFaceBase64 = enrollCanvas.toDataURL("image/jpeg", 0.95);
        selectedFaceFile = null;

        enrollPreviewImg.src = capturedFaceBase64;
        enrollPreviewBox.classList.remove("hidden");
        enrollWebcamPane.classList.add("hidden");
        stopEnrollCamera();
    });

    // Handle file upload
    enrollFileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        selectedFaceFile = file;
        capturedFaceBase64 = null;

        const reader = new FileReader();
        reader.onload = (event) => {
            enrollPreviewImg.src = event.target.result;
            enrollPreviewBox.classList.remove("hidden");
            enrollUploadPane.classList.add("hidden");
        };
        reader.readAsDataURL(file);
    });

    btnRetakeEnroll.addEventListener("click", () => {
        capturedFaceBase64 = null;
        selectedFaceFile = null;
        enrollPreviewBox.classList.add("hidden");
        switchToWebcamTab();
    });

    // 4. Modal Open & Close
    btnOpenRegister.addEventListener("click", () => {
        formEnroll.reset();
        capturedFaceBase64 = null;
        selectedFaceFile = null;
        enrollPreviewBox.classList.add("hidden");
        enrollErrorAlert.classList.add("hidden");
        modalEnroll.classList.remove("hidden");
        switchToWebcamTab();
    });

    function closeEnrollModal() {
        modalEnroll.classList.add("hidden");
        stopEnrollCamera();
    }

    btnCloseEnroll.addEventListener("click", closeEnrollModal);
    btnCancelEnroll.addEventListener("click", closeEnrollModal);

    // 5. Submit New User Enrollment
    formEnroll.addEventListener("submit", async (e) => {
        e.preventDefault();
        enrollErrorAlert.classList.add("hidden");

        if (!capturedFaceBase64 && !selectedFaceFile) {
            enrollErrorMsg.textContent = "Please capture or upload a face portrait for biometric matching.";
            enrollErrorAlert.classList.remove("hidden");
            return;
        }

        btnSubmitEnroll.disabled = true;
        btnSubmitEnroll.textContent = "Processing Face & Registering...";

        const formData = new FormData();
        formData.append("user_id", document.getElementById("new-user-id").value.trim());
        formData.append("full_name", document.getElementById("new-full-name").value.trim());
        formData.append("department", document.getElementById("new-department").value.trim());
        formData.append("role_title", document.getElementById("new-role-title").value.trim());
        formData.append("email", document.getElementById("new-email").value.trim());
        formData.append("phone", document.getElementById("new-phone").value.trim());
        formData.append("notes", document.getElementById("new-notes").value.trim());

        if (capturedFaceBase64) {
            formData.append("face_image_base64", capturedFaceBase64);
        } else if (selectedFaceFile) {
            formData.append("face_image_file", selectedFaceFile);
        }

        try {
            const resp = await fetch("/api/admin/users", {
                method: "POST",
                headers: getAuthHeaders(),
                body: formData
            });

            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || "Registration failed");
            }

            // Success!
            closeEnrollModal();
            loadUsers();
            loadStats();
        } catch (err) {
            enrollErrorMsg.textContent = err.message;
            enrollErrorAlert.classList.remove("hidden");
        } finally {
            btnSubmitEnroll.disabled = false;
            btnSubmitEnroll.textContent = "Complete Biometric Registration";
        }
    });

    // 6. Edit User Modal
    window.openEditModal = async function(userId) {
        try {
            const resp = await fetch(`/api/admin/users/${userId}`, {
                headers: getAuthHeaders()
            });
            if (!resp.ok) throw new Error("Could not fetch user details");
            const u = await resp.json();

            document.getElementById("edit-user-id").value = u.user_id;
            document.getElementById("edit-full-name").value = u.full_name;
            document.getElementById("edit-department").value = u.department || "";
            document.getElementById("edit-role_title").value = u.role_title || "";
            document.getElementById("edit-email").value = u.email || "";
            document.getElementById("edit-phone").value = u.phone || "";
            document.getElementById("edit-notes").value = u.notes || "";
            document.getElementById("edit-is-active").checked = u.is_active;

            modalEdit.classList.remove("hidden");
        } catch (e) {
            alert("Error: " + e.message);
        }
    };

    btnCloseEdit.addEventListener("click", () => modalEdit.classList.add("hidden"));
    btnCancelEdit.addEventListener("click", () => modalEdit.classList.add("hidden"));

    formEdit.addEventListener("submit", async (e) => {
        e.preventDefault();
        const userId = document.getElementById("edit-user-id").value;
        const updateData = {
            full_name: document.getElementById("edit-full-name").value.trim(),
            department: document.getElementById("edit-department").value.trim(),
            role_title: document.getElementById("edit-role-title").value.trim(),
            email: document.getElementById("edit-email").value.trim(),
            phone: document.getElementById("edit-phone").value.trim(),
            notes: document.getElementById("edit-notes").value.trim(),
            is_active: document.getElementById("edit-is-active").checked
        };

        try {
            const resp = await fetch(`/api/admin/users/${userId}`, {
                method: "PUT",
                headers: getAuthHeaders({ "Content-Type": "application/json" }),
                body: JSON.stringify(updateData)
            });
            if (!resp.ok) throw new Error("Update failed");
            modalEdit.classList.add("hidden");
            loadUsers();
            loadStats();
        } catch (e) {
            alert("Error: " + e.message);
        }
    });

    // 7. Delete User
    window.deleteUser = async function(userId, name) {
        if (!confirm(`Are you sure you want to permanently delete '${name}' (${userId})?`)) return;

        try {
            const resp = await fetch(`/api/admin/users/${userId}`, {
                method: "DELETE",
                headers: getAuthHeaders()
            });
            if (!resp.ok) throw new Error("Delete failed");
            loadUsers();
            loadStats();
        } catch (e) {
            alert("Error: " + e.message);
        }
    };

    // 8. System Settings Modal
    btnOpenSettings.addEventListener("click", () => modalSettings.classList.remove("hidden"));
    btnCloseSettings.addEventListener("click", () => modalSettings.classList.add("hidden"));

    thresholdSlider.addEventListener("input", (e) => {
        sliderThresholdVal.textContent = parseFloat(e.target.value).toFixed(3);
    });

    btnSaveThreshold.addEventListener("click", async () => {
        const val = parseFloat(thresholdSlider.value);
        try {
            const resp = await fetch("/api/admin/settings", {
                method: "POST",
                headers: getAuthHeaders({ "Content-Type": "application/json" }),
                body: JSON.stringify({ cosine_threshold: val })
            });
            if (resp.ok) {
                alert("Recognition threshold updated successfully!");
                modalSettings.classList.add("hidden");
            } else {
                alert("Failed to update threshold");
            }
        } catch (e) {
            alert("Error: " + e.message);
        }
    });

    formChangePwd.addEventListener("submit", async (e) => {
        e.preventDefault();
        const oldPwd = document.getElementById("old-password").value;
        const newPwd = document.getElementById("new-password").value;

        try {
            const resp = await fetch("/api/admin/change-password", {
                method: "POST",
                headers: getAuthHeaders({ "Content-Type": "application/json" }),
                body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
            });
            const data = await resp.json();
            if (resp.ok) {
                pwdChangeMsg.className = "text-xs text-emerald-400";
                pwdChangeMsg.textContent = "Password changed successfully!";
                pwdChangeMsg.classList.remove("hidden");
                formChangePwd.reset();
            } else {
                pwdChangeMsg.className = "text-xs text-rose-400";
                pwdChangeMsg.textContent = data.detail || "Error changing password";
                pwdChangeMsg.classList.remove("hidden");
            }
        } catch (e) {
            pwdChangeMsg.className = "text-xs text-rose-400";
            pwdChangeMsg.textContent = "Error: " + e.message;
            pwdChangeMsg.classList.remove("hidden");
        }
    });

    // 9. Initial Page Load
    btnRefreshUsers.addEventListener("click", () => {
        loadUsers();
        loadStats();
    });

    userSearchInput.addEventListener("input", debounce(loadUsers, 300));
    userDeptFilter.addEventListener("change", loadUsers);

    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    loadStats();
    loadUsers();
});
