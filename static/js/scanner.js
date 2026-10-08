/**
 * FaceID Kiosk Scanner Terminal Controller
 * Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
 * Author: Saitharun Cherukuri
 * Manages webcam streams, frame capture, API communication, and accuracy animations.
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const video = document.getElementById("webcam-feed");
    const canvas = document.getElementById("snapshot-canvas");
    const laserLine = document.getElementById("scanner-laser-line");
    const statusDot = document.getElementById("camera-status-dot");
    const statusText = document.getElementById("camera-status-text");
    const cameraError = document.getElementById("camera-error-message");
    const btnScanNow = document.getElementById("btn-scan-now");
    const scanBtnLabel = document.getElementById("scan-btn-label");
    const toggleAutoScan = document.getElementById("toggle-auto-scan");
    const fileUploadInput = document.getElementById("file-upload-input");
    const btnToggleMirror = document.getElementById("btn-toggle-mirror");
    const btnToggleSound = document.getElementById("btn-toggle-sound");
    const soundIcon = document.getElementById("sound-icon");

    // Result Panels
    const panelIdle = document.getElementById("panel-idle");
    const panelVerified = document.getElementById("panel-verified");
    const panelDenied = document.getElementById("panel-denied");
    const btnDismissVerified = document.getElementById("btn-dismiss-verified");
    const btnDismissDenied = document.getElementById("btn-dismiss-denied");

    // Verified Fields
    const accuracyNumber = document.getElementById("accuracy-number");
    const accuracyDonutStroke = document.getElementById("accuracy-donut-stroke");
    const matchConfidenceBadge = document.getElementById("match-confidence-badge");
    const userRegisteredPhoto = document.getElementById("user-registered-photo");
    const liveSnapshotPhoto = document.getElementById("live-snapshot-photo");
    const userFullName = document.getElementById("user-full-name");
    const userBadgeId = document.getElementById("user-badge-id");
    const userDepartment = document.getElementById("user-department");
    const userRoleTitle = document.getElementById("user-role-title");
    const verifiedTimestamp = document.getElementById("verified-timestamp");
    const resetTimerCount = document.getElementById("reset-timer-count");
    const deniedAccuracyVal = document.getElementById("denied-accuracy-val");

    // State Variables
    let stream = null;
    let isProcessing = false;
    let isMirrored = true;
    let autoScanInterval = null;
    let resetTimerInterval = null;
    let currentModalState = "idle"; // 'idle', 'verified', 'denied'

    // 1. Initialize Webcam
    async function startCamera() {
        statusText.textContent = "REQUESTING CAMERA...";
        statusDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: "user"
                },
                audio: false
            });

            video.srcObject = stream;
            await video.play();

            statusText.textContent = "CAMERA ACTIVE";
            statusDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
            laserLine.classList.remove("hidden");
            cameraError.classList.add("hidden");
        } catch (err) {
            console.error("Camera access failed:", err);
            statusText.textContent = "NO CAMERA ACCESS";
            statusDot.className = "w-2 h-2 rounded-full bg-rose-500";
            cameraError.classList.remove("hidden");
            laserLine.classList.add("hidden");
        }
    }

    startCamera();

    // 2. Camera View Helpers
    btnToggleMirror.addEventListener("click", () => {
        isMirrored = !isMirrored;
        if (isMirrored) {
            video.classList.add("-scale-x-100");
        } else {
            video.classList.remove("-scale-x-100");
        }
    });

    btnToggleSound.addEventListener("click", () => {
        window.soundEffects.enabled = !window.soundEffects.enabled;
        if (window.soundEffects.enabled) {
            soundIcon.className = "fa-solid fa-volume-high text-cyan-400";
        } else {
            soundIcon.className = "fa-solid fa-volume-xmark text-slate-500";
        }
    });

    // 3. Grab Frame Snapshot
    function captureFrame() {
        if (!video.videoWidth || !video.videoHeight) return null;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");

        // Respect mirror flip for proper orientation
        if (isMirrored) {
            ctx.translate(canvas.width, 0);
            ctx.scale(-1, 1);
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/jpeg", 0.9);
    }

    // 4. Animate Accuracy Number
    function animateAccuracyCounter(targetValue) {
        let current = 0;
        const step = targetValue / 25;
        const timer = setInterval(() => {
            current += step;
            if (current >= targetValue) {
                current = targetValue;
                clearInterval(timer);
            }
            accuracyNumber.textContent = current.toFixed(1);
        }, 20);

        // Update SVG Donut Stroke
        setTimeout(() => {
            accuracyDonutStroke.setAttribute("stroke-dasharray", `${targetValue}, 100`);
        }, 100);
    }

    // 5. Submit Face Scan to Backend
    async function performFaceScan(imageDataBase64) {
        if (isProcessing) return;
        isProcessing = true;

        // Visual and Audio feedback
        scanBtnLabel.textContent = "ANALYZING...";
        btnScanNow.disabled = true;
        window.soundEffects.playScan();

        try {
            const resp = await fetch("/api/scan-face", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: imageDataBase64 })
            });

            if (!resp.ok) {
                throw new Error(`Server returned HTTP ${resp.status}`);
            }

            const data = await resp.json();
            handleScanResult(data, imageDataBase64);
        } catch (err) {
            console.error("Scan error:", err);
            statusText.textContent = "SCAN ERROR - RETRYING";
            statusDot.className = "w-2 h-2 rounded-full bg-rose-400";
        } finally {
            isProcessing = false;
            scanBtnLabel.textContent = "SCAN FACE";
            btnScanNow.disabled = false;
        }
    }

    // 6. Handle Backend Result
    function handleScanResult(result, liveImageSrc) {
        clearInterval(resetTimerInterval);

        if (result.status === "VERIFIED") {
            currentModalState = "verified";
            window.soundEffects.playSuccess();

            // Populate Verified Details
            const user = result.user;
            userFullName.textContent = user.full_name || "Unknown";
            userBadgeId.textContent = user.user_id || "N/A";
            userDepartment.textContent = user.department || "General";
            userRoleTitle.textContent = user.role_title || "Verified Member";
            userRegisteredPhoto.src = user.photo_path || "";
            liveSnapshotPhoto.src = result.snapshot_url || liveImageSrc;
            verifiedTimestamp.textContent = result.timestamp || new Date().toLocaleTimeString();

            // Accuracy & Badge
            const acc = result.accuracy_percent || 0;
            animateAccuracyCounter(acc);

            if (acc >= 94) {
                matchConfidenceBadge.textContent = "EXACT MATCH (ULTRA-HIGH)";
                matchConfidenceBadge.className = "inline-block mt-1 text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-900/80 border border-emerald-500 text-emerald-200 font-bold uppercase";
            } else if (acc >= 85) {
                matchConfidenceBadge.textContent = "HIGH CONFIDENCE MATCH";
                matchConfidenceBadge.className = "inline-block mt-1 text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-900/60 border border-emerald-600/50 text-emerald-300 font-bold uppercase";
            } else {
                matchConfidenceBadge.textContent = "VERIFIED IDENTITY";
                matchConfidenceBadge.className = "inline-block mt-1 text-[10px] font-mono px-2 py-0.5 rounded-md bg-cyan-900/60 border border-cyan-600/50 text-cyan-300 font-bold uppercase";
            }

            // Show Verified Panel
            panelIdle.classList.add("hidden");
            panelDenied.classList.add("hidden");
            panelVerified.classList.remove("hidden");

            // Auto-reset countdown
            let countdown = 6;
            resetTimerCount.textContent = countdown;
            resetTimerInterval = setInterval(() => {
                countdown -= 1;
                resetTimerCount.textContent = countdown;
                if (countdown <= 0) {
                    clearInterval(resetTimerInterval);
                    resetToIdle();
                }
            }, 1000);

        } else if (result.status === "UNRECOGNIZED") {
            currentModalState = "denied";
            window.soundEffects.playError();

            deniedAccuracyVal.textContent = `${(result.accuracy_percent || 0).toFixed(1)}% (Score: ${result.similarity_score})`;

            panelIdle.classList.add("hidden");
            panelVerified.classList.add("hidden");
            panelDenied.classList.remove("hidden");

            // Auto-reset after 4 seconds
            let countdown = 4;
            resetTimerInterval = setInterval(() => {
                countdown -= 1;
                if (countdown <= 0) {
                    clearInterval(resetTimerInterval);
                    resetToIdle();
                }
            }, 1000);

        } else if (result.status === "NO_FACE") {
            statusText.textContent = "NO FACE DETECTED";
            statusDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-bounce";
            setTimeout(() => {
                if (stream) {
                    statusText.textContent = "CAMERA ACTIVE";
                    statusDot.className = "w-2 h-2 rounded-full bg-emerald-400 animate-ping";
                }
            }, 1500);
        } else if (result.status === "NO_REGISTERED_USERS") {
            alert("No registered users exist in the system yet. Please log into the Admin Portal to enroll users first.");
            resetToIdle();
        }
    }

    // 7. Reset View to Idle
    function resetToIdle() {
        clearInterval(resetTimerInterval);
        currentModalState = "idle";
        accuracyDonutStroke.setAttribute("stroke-dasharray", "0, 100");
        panelVerified.classList.add("hidden");
        panelDenied.classList.add("hidden");
        panelIdle.classList.remove("hidden");
    }

    btnDismissVerified.addEventListener("click", resetToIdle);
    btnDismissDenied.addEventListener("click", resetToIdle);

    // 8. Manual Scan Trigger
    btnScanNow.addEventListener("click", () => {
        const frame = captureFrame();
        if (frame) {
            performFaceScan(frame);
        } else {
            alert("Camera feed not ready. If camera is unavailable, please use the 'File' button to upload a photo.");
        }
    });

    // 9. Continuous Auto-Scan Mode
    toggleAutoScan.addEventListener("change", (e) => {
        if (e.target.checked) {
            autoScanInterval = setInterval(() => {
                // Only scan if idle and not currently showing results
                if (!isProcessing && currentModalState === "idle" && stream) {
                    const frame = captureFrame();
                    if (frame) {
                        performFaceScan(frame);
                    }
                }
            }, 2200);
        } else {
            if (autoScanInterval) {
                clearInterval(autoScanInterval);
                autoScanInterval = null;
            }
        }
    });

    // 10. File Upload Fallback
    fileUploadInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            const dataUrl = event.target.result;
            performFaceScan(dataUrl);
        };
        reader.readAsDataURL(file);
        // Reset file input value so re-selecting same file works
        e.target.value = "";
    });
});
