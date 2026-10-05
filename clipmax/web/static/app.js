// ClipMax Studio Web UI Application Logic
document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentClips = [];
  let selectedClip = null;
  let activeTab = "url";
  let localVideoPath = "";
  let ws = null;
  let pollInterval = null;

  // DOM Elements
  const tabUrl = document.getElementById("tabUrl");
  const tabLocal = document.getElementById("tabLocal");
  const viewUrl = document.getElementById("viewUrl");
  const viewLocal = document.getElementById("viewLocal");
  const inputUrl = document.getElementById("inputUrl");
  const dropZone = document.getElementById("dropZone");
  const lblLocalFile = document.getElementById("lblLocalFile");
  const fileVideoInput = document.getElementById("fileVideoInput");
  const boxAudioTracks = document.getElementById("boxAudioTracks");
  const selectAudioTrack = document.getElementById("selectAudioTrack");
  const lblAudioTrackCount = document.getElementById("lblAudioTrackCount");

  const inputEndpoint = document.getElementById("inputEndpoint");
  const inputApiKey = document.getElementById("inputApiKey");
  const selectModel = document.getElementById("selectModel");
  const btnRefreshModels = document.getElementById("btnRefreshModels");

  const inputTargetClips = document.getElementById("inputTargetClips");
  const selectDuration = document.getElementById("selectDuration");
  const selectClipMode = document.getElementById("selectClipMode");
  const inputRules = document.getElementById("inputRules");

  const selectColorPreset = document.getElementById("selectColorPreset");
  const inputBaseColor = document.getElementById("inputBaseColor");
  const lblBaseColor = document.getElementById("lblBaseColor");
  const inputHighlightColor = document.getElementById("inputHighlightColor");
  const lblHighlightColor = document.getElementById("lblHighlightColor");

  const btnGenerate = document.getElementById("btnGenerate");
  const btnCancel = document.getElementById("btnCancel");

  const stageStandby = document.getElementById("stageStandby");
  const stageProcessing = document.getElementById("stageProcessing");
  const stageReview = document.getElementById("stageReview");

  const processPct = document.getElementById("processPct");
  const progressBar = document.getElementById("progressBar");
  const processMsg = document.getElementById("processMsg");

  const mainVideo = document.getElementById("mainVideo");
  const btnPlayPause = document.getElementById("btnPlayPause");
  const iconPlay = document.getElementById("iconPlay");
  const iconPause = document.getElementById("iconPause");
  const videoScrubber = document.getElementById("videoScrubber");
  const timeDisplay = document.getElementById("timeDisplay");
  const btnMute = document.getElementById("btnMute");
  const muteIcon = document.getElementById("muteIcon");
  const volumeSlider = document.getElementById("volumeSlider");

  const activeClipTitle = document.getElementById("activeClipTitle");
  const activeClipScore = document.getElementById("activeClipScore");
  const activeClipHook = document.getElementById("activeClipHook");
  const activeClipReason = document.getElementById("activeClipReason");
  const btnCopyHook = document.getElementById("btnCopyHook");
  const btnCopyReason = document.getElementById("btnCopyReason");
  const btnCopyAll = document.getElementById("btnCopyAll");

  const clipsCount = document.getElementById("clipsCount");
  const clipsGallery = document.getElementById("clipsGallery");
  const btnExportSingle = document.getElementById("btnExportSingle");
  const btnExportAll = document.getElementById("btnExportAll");
  const btnNewTask = document.getElementById("btnNewTask");

  const hwPill = document.getElementById("hwPill");
  const hwPillText = document.getElementById("hwPillText");
  const btnResetClear = document.getElementById("btnResetClear");
  const btnMin = document.getElementById("btnMin");
  const btnClose = document.getElementById("btnClose");

  // Video Canvas Box Container for Draggable Overlays
  const videoCanvasBox = document.getElementById("videoCanvasBox");

  // Video Text Overlay Elements
  const liveTextOverlay = document.getElementById("liveTextOverlay");
  const liveTextContent = document.getElementById("liveTextContent");
  const textResizeHandle = document.getElementById("textResizeHandle");
  const inputOverlayText = document.getElementById("inputOverlayText");
  const selectOverlayFont = document.getElementById("selectOverlayFont");
  const pickerOverlayTextColor = document.getElementById("pickerOverlayTextColor");
  const lblOverlayTextColor = document.getElementById("lblOverlayTextColor");
  const inputRangeTextSize = document.getElementById("inputRangeTextSize");
  const lblOverlayFontSize = document.getElementById("lblOverlayFontSize");
  const selectOverlayBgStyle = document.getElementById("selectOverlayBgStyle");
  const btnApplyOverlay = document.getElementById("btnApplyOverlay");
  const lblApplyOverlay = document.getElementById("lblApplyOverlay");
  const btnRemoveOverlay = document.getElementById("btnRemoveOverlay");
  const badgeOverlayStatus = document.getElementById("badgeOverlayStatus");

  // Free Roam Text Coordinates & Presets
  const inputRangeTextX = document.getElementById("inputRangeTextX");
  const inputRangeTextY = document.getElementById("inputRangeTextY");
  const lblTextPosX = document.getElementById("lblTextPosX");
  const lblTextPosY = document.getElementById("lblTextPosY");
  const btnPosPresetTop = document.getElementById("btnPosPresetTop");
  const btnPosPresetCenter = document.getElementById("btnPosPresetCenter");
  const btnPosPresetBottom = document.getElementById("btnPosPresetBottom");

  // Image / Logo Overlay Elements
  const liveImageOverlayContainer = document.getElementById("liveImageOverlayContainer");
  const liveImageOverlay = document.getElementById("liveImageOverlay");
  const imageResizeHandle = document.getElementById("imageResizeHandle");
  const fileImageInput = document.getElementById("fileImageInput");
  const btnPickImage = document.getElementById("btnPickImage");
  const lblImageFileName = document.getElementById("lblImageFileName");
  const btnClearImage = document.getElementById("btnClearImage");
  const imageControlsWrapper = document.getElementById("imageControlsWrapper");
  const inputRangeImageScale = document.getElementById("inputRangeImageScale");
  const lblImageScale = document.getElementById("lblImageScale");
  const inputRangeImageOpacity = document.getElementById("inputRangeImageOpacity");
  const lblImageOpacity = document.getElementById("lblImageOpacity");
  const inputRangeImageX = document.getElementById("inputRangeImageX");
  const lblImagePosX = document.getElementById("lblImagePosX");
  const inputRangeImageY = document.getElementById("inputRangeImageY");
  const lblImagePosY = document.getElementById("lblImagePosY");
  const btnImgPresetTopRight = document.getElementById("btnImgPresetTopRight");
  const btnImgPresetTopLeft = document.getElementById("btnImgPresetTopLeft");
  const btnImgPresetBottomRight = document.getElementById("btnImgPresetBottomRight");
  const btnImgPresetCenter = document.getElementById("btnImgPresetCenter");
  const btnApplyImageOverlay = document.getElementById("btnApplyImageOverlay");
  const lblApplyImageOverlay = document.getElementById("lblApplyImageOverlay");
  const btnRemoveImageOverlay = document.getElementById("btnRemoveImageOverlay");
  const badgeImageOverlayStatus = document.getElementById("badgeImageOverlayStatus");

  let currentImageOverlayServerPath = "";

  // Multi-Page Containers
  const pageHome = document.getElementById("pageHome");
  const pageMedia = document.getElementById("pageMedia");
  const pageCuration = document.getElementById("pageCuration");
  const pageStyling = document.getElementById("pageStyling");
  const pageStudio = document.getElementById("pageStudio");

  // Stepper Header Tabs
  const navTabHome = document.getElementById("navTabHome");
  const navTabMedia = document.getElementById("navTabMedia");
  const navTabCuration = document.getElementById("navTabCuration");
  const navTabStyling = document.getElementById("navTabStyling");
  const navTabStudio = document.getElementById("navTabStudio");
  const studioBadgeDot = document.getElementById("studioBadgeDot");

  // Page Navigation Buttons
  const btnStartNewProject = document.getElementById("btnStartNewProject");
  const btnCancelFromMedia = document.getElementById("btnCancelFromMedia");
  const btnNextToCuration = document.getElementById("btnNextToCuration");
  const btnBackToMedia = document.getElementById("btnBackToMedia");
  const btnNextToStyling = document.getElementById("btnNextToStyling");
  const btnBackToCuration = document.getElementById("btnBackToCuration");
  const btnEmptyStartProject = document.getElementById("btnEmptyStartProject");
  const btnStandbyGoToMedia = document.getElementById("btnStandbyGoToMedia");

  // Last Project & History Elements
  const lastProjectSection = document.getElementById("lastProjectSection");
  const lastProjectCard = document.getElementById("lastProjectCard");
  const lastProjectThumb = document.getElementById("lastProjectThumb");
  const lastProjectThumbPlaceholder = document.getElementById("lastProjectThumbPlaceholder");
  const lastProjectBadgeMode = document.getElementById("lastProjectBadgeMode");
  const lastProjectDate = document.getElementById("lastProjectDate");
  const lastProjectTitle = document.getElementById("lastProjectTitle");
  const lastProjectSource = document.getElementById("lastProjectSource");
  const lastProjectClipsCount = document.getElementById("lastProjectClipsCount");
  const btnOpenLastProject = document.getElementById("btnOpenLastProject");
  const totalProjectsCount = document.getElementById("totalProjectsCount");
  const btnRefreshProjects = document.getElementById("btnRefreshProjects");
  const projectHistoryEmpty = document.getElementById("projectHistoryEmpty");
  const projectHistoryList = document.getElementById("projectHistoryList");

  let currentPage = "home";

  function showPage(targetPage) {
    currentPage = targetPage;
    const pages = {
      home: pageHome,
      media: pageMedia,
      curation: pageCuration,
      styling: pageStyling,
      studio: pageStudio
    };

    const tabs = {
      home: navTabHome,
      media: navTabMedia,
      curation: navTabCuration,
      styling: navTabStyling,
      studio: navTabStudio
    };

    Object.keys(pages).forEach(key => {
      if (pages[key]) {
        if (key === targetPage) {
          pages[key].classList.remove("hidden");
        } else {
          pages[key].classList.add("hidden");
        }
      }
    });

    Object.keys(tabs).forEach(key => {
      if (tabs[key]) {
        if (key === targetPage) {
          tabs[key].className = "flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-semibold transition text-white bg-[#1E2538] shadow-sm";
        } else {
          tabs[key].className = "flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition text-gray-400 hover:text-gray-200";
        }
      }
    });

    if (targetPage === "home") {
      loadProjectHistory();
    }
  }

  // Wire Stepper Tabs
  if (navTabHome) navTabHome.addEventListener("click", () => showPage("home"));
  if (navTabMedia) navTabMedia.addEventListener("click", () => showPage("media"));
  if (navTabCuration) navTabCuration.addEventListener("click", () => showPage("curation"));
  if (navTabStyling) navTabStyling.addEventListener("click", () => showPage("styling"));
  if (navTabStudio) navTabStudio.addEventListener("click", () => showPage("studio"));

  // Stepper Flow Buttons
  if (btnStartNewProject) btnStartNewProject.addEventListener("click", () => showPage("media"));
  if (btnEmptyStartProject) btnEmptyStartProject.addEventListener("click", () => showPage("media"));
  if (btnStandbyGoToMedia) btnStandbyGoToMedia.addEventListener("click", () => showPage("media"));
  if (btnCancelFromMedia) btnCancelFromMedia.addEventListener("click", () => showPage("home"));

  if (btnNextToCuration) {
    btnNextToCuration.addEventListener("click", () => {
      const source = activeTab === "url" ? inputUrl.value.trim() : localVideoPath.trim();
      if (!source) {
        alert(activeTab === "url" ? "Harap masukkan URL YouTube terlebih dahulu." : "Harap pilih file video lokal terlebih dahulu.");
        return;
      }
      showPage("curation");
    });
  }

  if (btnBackToMedia) btnBackToMedia.addEventListener("click", () => showPage("media"));
  if (btnNextToStyling) btnNextToStyling.addEventListener("click", () => showPage("styling"));
  if (btnBackToCuration) btnBackToCuration.addEventListener("click", () => showPage("curation"));

  // --- Project History Logic ---
  async function loadProjectHistory() {
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) return;
      const data = await res.json();
      const projects = data.projects || [];

      if (totalProjectsCount) totalProjectsCount.textContent = projects.length;

      if (projects.length === 0) {
        if (projectHistoryEmpty) projectHistoryEmpty.classList.remove("hidden");
        if (lastProjectSection) lastProjectSection.classList.add("hidden");
        if (projectHistoryList) projectHistoryList.innerHTML = "";
        return;
      }

      if (projectHistoryEmpty) projectHistoryEmpty.classList.add("hidden");
      if (lastProjectSection) lastProjectSection.classList.remove("hidden");

      // Last Project (First in list)
      const last = projects[0];
      if (lastProjectTitle) lastProjectTitle.textContent = last.title;
      if (lastProjectDate) lastProjectDate.textContent = last.created_at;
      if (lastProjectClipsCount) lastProjectClipsCount.textContent = `${last.clip_count} Klip Siap Di-review`;
      if (lastProjectSource) lastProjectSource.textContent = last.input_source;
      if (lastProjectBadgeMode) {
        lastProjectBadgeMode.textContent = last.clip_mode === "montage" ? "Multi-Cut Montage" : "Single Clip";
      }

      if (last.cover_thumbnail && lastProjectThumb && lastProjectThumbPlaceholder) {
        lastProjectThumb.src = `${last.cover_thumbnail}?t=${Date.now()}`;
        lastProjectThumb.classList.remove("hidden");
        lastProjectThumbPlaceholder.classList.add("hidden");
      } else if (lastProjectThumb && lastProjectThumbPlaceholder) {
        lastProjectThumb.classList.add("hidden");
        lastProjectThumbPlaceholder.classList.remove("hidden");
      }

      if (btnOpenLastProject) {
        btnOpenLastProject.onclick = () => loadProject(last.project_id);
      }

      // Render full list
      if (projectHistoryList) {
        projectHistoryList.innerHTML = "";
        projects.forEach(p => {
          const item = document.createElement("div");
          item.className = "p-3.5 rounded-xl bg-[#131722] border border-[#222938] hover:border-[#374151] transition flex items-center space-x-3.5 shadow";
          
          const thumbUrl = p.cover_thumbnail ? `${p.cover_thumbnail}?t=${Date.now()}` : "";
          const isMontage = p.clip_mode === "montage";

          item.innerHTML = `
            <div class="w-14 h-20 bg-black rounded-lg overflow-hidden shrink-0 border border-[#252E42] flex items-center justify-center">
              ${thumbUrl ? `<img src="${thumbUrl}" class="w-full h-full object-cover">` : '<span class="text-[10px] text-gray-500 font-mono">9:16</span>'}
            </div>
            <div class="flex-1 min-w-0 space-y-1">
              <div class="flex items-center space-x-2">
                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${isMontage ? 'bg-purple-900/60 text-purple-300' : 'bg-indigo-950 text-indigo-300'}">
                  ${isMontage ? 'Montage' : 'Single'}
                </span>
                <span class="text-[11px] text-gray-400 font-mono">${p.created_at}</span>
              </div>
              <h4 class="text-xs font-bold text-gray-200 truncate">${p.title}</h4>
              <p class="text-[11px] text-gray-500 truncate">${p.input_source}</p>
              <div class="text-[10px] text-emerald-400 font-medium">🎬 ${p.clip_count} Klip</div>
            </div>
            <div class="flex items-center space-x-2 shrink-0">
              <button class="btn-load-proj px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition shadow">
                Buka Proyek
              </button>
              <button class="btn-del-proj p-1.5 text-gray-500 hover:text-red-400 rounded-lg hover:bg-red-950/30 transition" title="Hapus Proyek">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>
          `;

          item.querySelector(".btn-load-proj").addEventListener("click", () => loadProject(p.project_id));
          item.querySelector(".btn-del-proj").addEventListener("click", async () => {
            if (confirm(`Yakin ingin menghapus proyek "${p.title}"?`)) {
              await fetch(`/api/projects/${p.project_id}`, { method: "DELETE" });
              loadProjectHistory();
            }
          });

          projectHistoryList.appendChild(item);
        });
      }
    } catch (e) {
      console.warn("Failed to load project history:", e);
    }
  }

  async function loadProject(projectId) {
    try {
      const res = await fetch(`/api/projects/${projectId}/load`, { method: "POST" });
      if (!res.ok) {
        alert("Gagal memuat proyek. File mungkin sudah dipindahkan.");
        return;
      }
      const data = await res.json();
      currentClips = data.clips || [];

      if (studioBadgeDot) studioBadgeDot.classList.remove("hidden");

      showPage("studio");
      showStage("review");

      if (currentClips.length > 0) {
        renderClipsGallery(currentClips);
        selectClip(currentClips[0]);
      }
    } catch (e) {
      console.error("Error loading project:", e);
      alert(`Error loading project: ${e.message}`);
    }
  }

  if (btnRefreshProjects) {
    btnRefreshProjects.addEventListener("click", loadProjectHistory);
  }

  // Step Indicators
  const stepElements = {
    ingest: document.getElementById("step-ingest"),
    transcribe: document.getElementById("step-transcribe"),
    ai: document.getElementById("step-ai"),
    reframe: document.getElementById("step-reframe"),
    render: document.getElementById("step-render"),
    complete: document.getElementById("step-complete")
  };

  // 1. Tab Switching
  tabUrl.addEventListener("click", () => {
    activeTab = "url";
    tabUrl.className = "py-1.5 text-xs font-medium rounded-md transition-all text-white bg-[#1E2330] shadow-sm";
    tabLocal.className = "py-1.5 text-xs font-medium rounded-md transition-all text-gray-400 hover:text-gray-200";
    viewUrl.classList.remove("hidden");
    viewLocal.classList.add("hidden");
  });

  tabLocal.addEventListener("click", () => {
    activeTab = "local";
    tabLocal.className = "py-1.5 text-xs font-medium rounded-md transition-all text-white bg-[#1E2330] shadow-sm";
    tabUrl.className = "py-1.5 text-xs font-medium rounded-md transition-all text-gray-400 hover:text-gray-200";
    viewLocal.classList.remove("hidden");
    viewUrl.classList.add("hidden");
  });

  // 2. Local Video Picker
  dropZone.addEventListener("click", async () => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_video_file) {
      try {
        const picked = await window.pywebview.api.choose_video_file();
        if (picked) {
          localVideoPath = picked;
          lblLocalFile.textContent = picked.split(/[\\/]/).pop();
          lblLocalFile.title = picked;
          return;
        }
      } catch (e) {
        console.warn("Desktop video dialog error:", e);
      }
    }
    fileVideoInput.click();
  });

  fileVideoInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      localVideoPath = f.name;
      lblLocalFile.textContent = f.name;
    }
  });

  // YouTube Multi-Language Audio Tracks Probing
  let audioTracksTimer = null;
  async function checkAudioTracks(rawUrl) {
    const url = (rawUrl || "").trim();
    if (!url || !url.startsWith("http")) {
      if (boxAudioTracks) boxAudioTracks.classList.add("hidden");
      if (selectAudioTrack) selectAudioTrack.innerHTML = '<option value="default">Default / Original</option>';
      return;
    }

    try {
      if (boxAudioTracks) boxAudioTracks.classList.remove("hidden");
      if (lblAudioTrackCount) {
        lblAudioTrackCount.textContent = "Mengecek Trek Audio...";
        lblAudioTrackCount.className = "text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-indigo-950/80 text-indigo-400 border border-indigo-500/30";
      }

      const res = await fetch("/api/youtube/audio-tracks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
      });
      if (!res.ok) {
        if (boxAudioTracks) boxAudioTracks.classList.add("hidden");
        return;
      }
      const data = await res.json();
      const tracks = data.tracks || [];

      if (tracks.length > 1) {
        if (boxAudioTracks) boxAudioTracks.classList.remove("hidden");
        if (lblAudioTrackCount) {
          lblAudioTrackCount.textContent = `${tracks.length} Bahasa Tersedia`;
          lblAudioTrackCount.className = "text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-500/30";
        }
        if (selectAudioTrack) {
          selectAudioTrack.innerHTML = "";
          tracks.forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.code;
            opt.textContent = `${t.label}${t.is_original ? " ⭐" : ""}`;
            selectAudioTrack.appendChild(opt);
          });
        }
      } else {
        if (boxAudioTracks) boxAudioTracks.classList.add("hidden");
        if (selectAudioTrack) selectAudioTrack.innerHTML = '<option value="default">Default / Original</option>';
      }
    } catch (e) {
      console.warn("Audio tracks probe failed:", e);
      if (boxAudioTracks) boxAudioTracks.classList.add("hidden");
    }
  }

  if (inputUrl) {
    inputUrl.addEventListener("input", () => {
      clearTimeout(audioTracksTimer);
      audioTracksTimer = setTimeout(() => {
        checkAudioTracks(inputUrl.value);
      }, 700);
    });
    inputUrl.addEventListener("paste", () => {
      setTimeout(() => {
        checkAudioTracks(inputUrl.value);
      }, 100);
    });
    inputUrl.addEventListener("change", () => {
      checkAudioTracks(inputUrl.value);
    });
  }

  // 4. Initial System & Config Loading
  async function loadInitialData() {
    try {
      const sysRes = await fetch("/api/system");
      const sysData = await sysRes.json();
      if (sysData.cuda_available) {
        hwPillText.textContent = "NVIDIA RTX 3050 | CUDA Active";
      } else {
        hwPillText.textContent = "CPU Only (CUDA Inactive)";
        hwPill.querySelector("span").className = "w-2 h-2 rounded-full bg-amber-500 mr-2";
      }

      const cfgRes = await fetch("/api/config");
      const cfg = await cfgRes.json();
      inputEndpoint.value = cfg.endpoint_url || "http://localhost:20128/v1";
      inputApiKey.value = cfg.api_key || "";
      inputTargetClips.value = cfg.target_clip_count || 3;
      
      // Auto-clear form state on initial load / DOM ready
      inputUrl.value = "";
      inputRules.value = "";
      localVideoPath = "";
      lblLocalFile.textContent = "Pilih video MP4 dari komputer...";
      localStorage.removeItem("clipmax_campaign_brief");
      localStorage.removeItem("clipmax_youtube_url");

      if (selectClipMode && cfg.clip_mode) {
        selectClipMode.value = cfg.clip_mode;
      }

      if (cfg.subtitle_base_color && inputBaseColor) {
        inputBaseColor.value = cfg.subtitle_base_color;
        lblBaseColor.textContent = cfg.subtitle_base_color.toUpperCase();
      }
      if (cfg.subtitle_highlight_color && inputHighlightColor) {
        inputHighlightColor.value = cfg.subtitle_highlight_color;
        lblHighlightColor.textContent = cfg.subtitle_highlight_color.toUpperCase();
      }
      if (cfg.subtitle_color_preset && selectColorPreset) {
        selectColorPreset.value = cfg.subtitle_color_preset;
      }

      await refreshModels(cfg.selected_model);
    } catch (e) {
      console.warn("Error loading config:", e);
    }
  }

  // 5. Model Discovery
  async function refreshModels(preferredModel) {
    try {
      btnRefreshModels.classList.add("animate-spin");
      const res = await fetch("/api/models");
      const data = await res.json();
      selectModel.innerHTML = "";
      (data.models || ["default"]).forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === preferredModel) opt.selected = true;
        selectModel.appendChild(opt);
      });
    } catch (e) {
      console.warn("Model discovery error:", e);
    } finally {
      btnRefreshModels.classList.remove("animate-spin");
    }
  }
  btnRefreshModels.addEventListener("click", () => refreshModels(selectModel.value));

  // 6. WebSocket Setup
  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress`);

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        handlePipelineMessage(data);
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 2000);
    };
  }

  function handlePipelineMessage(data) {
    if (data.type === "progress") {
      updateProgressUI(data.status, data.progress, data.message);
    } else if (data.type === "complete") {
      onPipelineComplete(data.clips || []);
    } else if (data.type === "error") {
      onPipelineError(data.message);
    } else if (data.type === "cancelled") {
      onPipelineCancelled();
    } else if (data.type === "state") {
      if (data.status && data.status !== "IDLE" && data.status !== "COMPLETED" && data.status !== "FAILED") {
        showStage("processing");
        updateProgressUI(data.status, data.progress, data.message);
      } else if (data.status === "COMPLETED" && data.clips && data.clips.length > 0) {
        onPipelineComplete(data.clips);
      }
    }
  }

  function highlightStep(activeStepKey) {
    Object.keys(stepElements).forEach((key) => {
      const el = stepElements[key];
      if (!el) return;
      if (key === activeStepKey) {
        el.className = "p-2 rounded bg-indigo-950/70 border border-indigo-500/60 text-center text-indigo-300 font-semibold shadow-sm";
      } else {
        el.className = "p-2 rounded bg-[#0E121A] border border-[#222938] text-center text-gray-500 font-normal";
      }
    });
  }

  function updateProgressUI(status, pct, msg) {
    showStage("processing");
    processPct.textContent = `${pct}%`;
    progressBar.style.width = `${pct}%`;
    processMsg.textContent = msg;

    if (status === "DOWNLOADING") highlightStep("ingest");
    else if (status === "EXTRACTING_AUDIO" || status === "TRANSCRIBING") highlightStep("transcribe");
    else if (status === "AI_EVALUATING") highlightStep("ai");
    else if (status === "TRACKING_FACES") highlightStep("reframe");
    else if (status === "RENDERING") highlightStep("render");
    else if (status === "COMPLETED") highlightStep("complete");
  }

  function showStage(stageName) {
    stageStandby.classList.add("hidden");
    stageProcessing.classList.add("hidden");
    stageReview.classList.add("hidden");

    if (stageName === "standby") stageStandby.classList.remove("hidden");
    else if (stageName === "processing") {
      stageProcessing.classList.remove("hidden");
      btnGenerate.classList.add("hidden");
      btnCancel.classList.remove("hidden");
    } else if (stageName === "review") {
      stageReview.classList.remove("hidden");
      btnGenerate.classList.remove("hidden");
      btnCancel.classList.add("hidden");
    }
  }

  // Color Preset Definitions & Handlers
  const colorPresets = {
    red_white: { highlight: "#FF2A2A", base: "#FFFFFF" },
    tiktok_yellow: { highlight: "#FFE81F", base: "#FFFFFF" },
    neon_green: { highlight: "#39FF14", base: "#FFFFFF" },
    cyan_gamer: { highlight: "#00F0FF", base: "#FFFFFF" }
  };

  if (selectColorPreset) {
    selectColorPreset.addEventListener("change", () => {
      const p = colorPresets[selectColorPreset.value];
      if (p) {
        inputHighlightColor.value = p.highlight;
        lblHighlightColor.textContent = p.highlight;
        inputBaseColor.value = p.base;
        lblBaseColor.textContent = p.base;
      }
    });
  }

  if (inputBaseColor) {
    inputBaseColor.addEventListener("input", () => {
      lblBaseColor.textContent = inputBaseColor.value.toUpperCase();
      selectColorPreset.value = "custom";
    });
  }

  if (inputHighlightColor) {
    inputHighlightColor.addEventListener("input", () => {
      lblHighlightColor.textContent = inputHighlightColor.value.toUpperCase();
      selectColorPreset.value = "custom";
    });
  }

  // 7. Start Pipeline
  btnGenerate.addEventListener("click", async () => {
    const inputSource = activeTab === "url" ? inputUrl.value.trim() : localVideoPath.trim();
    if (!inputSource) {
      alert(activeTab === "url" ? "Harap masukkan URL YouTube terlebih dahulu." : "Harap pilih file video lokal terlebih dahulu.");
      return;
    }

    // Save config first
    let minD = 30, maxD = 60;
    const durVal = selectDuration.value;
    if (durVal === "short") { minD = 15; maxD = 30; }
    else if (durVal === "long") { minD = 60; maxD = 90; }
    const clipModeVal = selectClipMode ? selectClipMode.value : "single";
    const subBaseVal = inputBaseColor ? inputBaseColor.value : "#FFFFFF";
    const subHighlightVal = inputHighlightColor ? inputHighlightColor.value : "#FF2A2A";
    const subPresetVal = selectColorPreset ? selectColorPreset.value : "red_white";

    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint_url: inputEndpoint.value.trim(),
        api_key: inputApiKey.value.trim(),
        selected_model: selectModel.value,
        target_clip_count: parseInt(inputTargetClips.value) || 3,
        duration_preset: durVal,
        min_duration: minD,
        max_duration: maxD,
        campaign_rules: inputRules.value.trim(),
        clip_mode: clipModeVal,
        subtitle_base_color: subBaseVal,
        subtitle_highlight_color: subHighlightVal,
        subtitle_color_preset: subPresetVal
      })
    });

    // Start pipeline
    try {
      showPage("studio");
      showStage("processing");
      if (studioBadgeDot) studioBadgeDot.classList.remove("hidden");
      updateProgressUI("STARTING", 5, "Mempersiapkan pipeline...");

      const selectedAudioLang = (activeTab === "url" && selectAudioTrack && selectAudioTrack.value !== "default") 
        ? selectAudioTrack.value 
        : null;

      const res = await fetch("/api/pipeline/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_source: inputSource,
          target_clip_count: parseInt(inputTargetClips.value) || 3,
          min_duration: minD,
          max_duration: maxD,
          campaign_rules: inputRules.value.trim(),
          clip_mode: clipModeVal,
          subtitle_base_color: subBaseVal,
          subtitle_highlight_color: subHighlightVal,
          audio_language: selectedAudioLang
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal memulai pipeline");
      }
    } catch (e) {
      alert("Error: " + e.message);
      showStage("standby");
    }
  });

  // 8. Cancel Pipeline
  btnCancel.addEventListener("click", async () => {
    btnCancel.disabled = true;
    btnCancel.textContent = "Membatalkan...";
    try {
      await fetch("/api/pipeline/cancel", { method: "POST" });
    } catch (e) {
      console.warn("Cancel error:", e);
    } finally {
      btnCancel.disabled = false;
      btnCancel.textContent = "Batalkan Proses";
    }
  });

  function onPipelineCancelled() {
    showStage("standby");
    btnGenerate.classList.remove("hidden");
    btnCancel.classList.add("hidden");
  }

  function cleanErrorText(text) {
    if (!text) return "";
    return text
      .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "")
      .replace(/(?:\[\]|\[)[0-9;]+m/g, "")
      .replace(/\[0m/g, "")
      .trim();
  }

  function onPipelineError(msg) {
    alert("Pipeline terhenti:\n" + cleanErrorText(msg));
    showStage("standby");
    btnGenerate.classList.remove("hidden");
    btnCancel.classList.add("hidden");
  }

  function onPipelineComplete(clips) {
    currentClips = clips;
    showPage("studio");
    showStage("review");
    if (studioBadgeDot) studioBadgeDot.classList.remove("hidden");
    renderClipsGallery(clips);
    if (clips.length > 0) {
      selectClip(clips[0]);
    }
    loadProjectHistory();
  }

  // 9. Review Workspace & Gallery
  function renderClipsGallery(clips) {
    clipsCount.textContent = clips.length;
    clipsGallery.innerHTML = "";

    clips.forEach((clip, idx) => {
      const card = document.createElement("div");
      const isSelected = selectedClip && selectedClip.clip_id === clip.clip_id;
      const score = clip.virality_score || 0;
      const isHigh = score >= 90;

      card.className = `p-2.5 rounded-lg border cursor-pointer transition-all flex space-x-3 items-center ${
        isSelected
          ? "bg-[#1C2230] border-indigo-500 shadow-md shadow-indigo-500/20"
          : "bg-[#151923] border-[#222938] hover:border-[#374151]"
      }`;

      // Thumbnail url with dynamic fallback endpoint
      const thumbSrc = `/api/clips/${clip.clip_id}/thumbnail?t=${Date.now()}`;

      const durSec = Math.round((clip.end_time || 0) - (clip.start_time || 0));

      card.innerHTML = `
        <div class="w-12 h-20 bg-black rounded overflow-hidden shrink-0 border border-[#2A3345] flex items-center justify-center">
          ${thumbSrc ? `<img src="${thumbSrc}" class="w-full h-full object-cover">` : '<span class="text-[10px] text-gray-500">9:16</span>'}
        </div>
        <div class="flex-1 min-w-0 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-semibold text-xs text-gray-200 truncate">#${clip.clip_id} ${clip.title}</span>
            <span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
              isHigh ? "bg-amber-500/20 text-amber-300 border border-amber-500/40" : "bg-indigo-950 text-indigo-300"
            }">${score}</span>
          </div>
          <p class="text-[11px] text-indigo-300 italic truncate">${clip.hook || ""}</p>
          <div class="flex items-center space-x-2 text-[10px] text-gray-400">
            <span>⏱ ${durSec}s</span>
            <span>•</span>
            ${clip.reframe_mode === "MONTAGE" 
              ? '<span class="px-1.5 py-0.2 rounded bg-purple-900/60 text-purple-300 font-medium text-[9px]">✂ Multi-Cut Montage</span>' 
              : `<span class="truncate">${clip.reframe_mode || "Crop 9:16"}</span>`}
          </div>
        </div>
      `;

      card.addEventListener("click", () => selectClip(clip));
      clipsGallery.appendChild(card);
    });
  }

  function selectClip(clip) {
    selectedClip = clip;
    const streamUrl = `/api/clips/${clip.clip_id}/stream?t=${Date.now()}`;
    mainVideo.src = streamUrl;
    mainVideo.load();
    mainVideo.play().catch(() => {});

    activeClipTitle.textContent = `#${clip.clip_id} ${clip.title}`;
    activeClipScore.textContent = `${clip.virality_score} Score`;
    activeClipHook.textContent = `"${clip.hook || ""}"`;
    activeClipReason.textContent = clip.reasoning || "Tidak ada deskripsi tambahan.";

    // Reset or populate overlay settings for this clip
    if (inputOverlayText) {
      inputOverlayText.value = clip.overlay_text || "";
      if (selectOverlayFont) selectOverlayFont.value = clip.overlay_font || "Montserrat";
      if (inputRangeTextX) {
        inputRangeTextX.value = clip.overlay_x_pct !== undefined ? clip.overlay_x_pct : 50;
        if (lblTextPosX) lblTextPosX.textContent = `${inputRangeTextX.value}%`;
      }
      if (inputRangeTextY) {
        inputRangeTextY.value = clip.overlay_y_pct !== undefined ? clip.overlay_y_pct : 12;
        if (lblTextPosY) lblTextPosY.textContent = `${inputRangeTextY.value}%`;
      }
      if (inputRangeTextSize) {
        inputRangeTextSize.value = clip.overlay_font_size || 56;
        if (lblOverlayFontSize) lblOverlayFontSize.textContent = `${inputRangeTextSize.value}px`;
      }
      if (pickerOverlayTextColor) {
        pickerOverlayTextColor.value = clip.overlay_text_color || "#FFFFFF";
        if (lblOverlayTextColor) lblOverlayTextColor.textContent = pickerOverlayTextColor.value.toUpperCase();
      }
      if (selectOverlayBgStyle) selectOverlayBgStyle.value = clip.overlay_bg_style || "solid_black";
      if (badgeOverlayStatus) {
        badgeOverlayStatus.textContent = clip.has_overlay ? "Terbakar di Video" : "Live Preview";
        badgeOverlayStatus.className = clip.has_overlay ? "text-[10px] text-emerald-400 font-mono" : "text-[10px] text-gray-400 font-mono";
      }
      updateLiveOverlayPreview();
    }

    // Reset or populate image overlay settings
    if (imageControlsWrapper) {
      if (clip.image_overlay_path) {
        currentImageOverlayServerPath = clip.image_overlay_path;
        if (lblImageFileName) lblImageFileName.textContent = clip.image_overlay_name || "logo.png";
        if (btnClearImage) btnClearImage.classList.remove("hidden");
        imageControlsWrapper.classList.remove("opacity-50", "pointer-events-none");
        if (inputRangeImageScale) {
          inputRangeImageScale.value = clip.image_scale_pct || 16;
          if (lblImageScale) lblImageScale.textContent = `${inputRangeImageScale.value}%`;
        }
        if (inputRangeImageOpacity) {
          inputRangeImageOpacity.value = clip.image_opacity ? Math.round(clip.image_opacity * 100) : 90;
          if (lblImageOpacity) lblImageOpacity.textContent = `${inputRangeImageOpacity.value}%`;
        }
        if (inputRangeImageX) {
          inputRangeImageX.value = clip.image_x_pct !== undefined ? clip.image_x_pct : 85;
          if (lblImagePosX) lblImagePosX.textContent = `${inputRangeImageX.value}%`;
        }
        if (inputRangeImageY) {
          inputRangeImageY.value = clip.image_y_pct !== undefined ? clip.image_y_pct : 8;
          if (lblImagePosY) lblImagePosY.textContent = `${inputRangeImageY.value}%`;
        }
        if (badgeImageOverlayStatus) {
          badgeImageOverlayStatus.textContent = clip.has_image_overlay ? "Terbakar di Video" : "Live Preview";
          badgeImageOverlayStatus.className = clip.has_image_overlay ? "text-[10px] text-cyan-400 font-mono" : "text-[10px] text-gray-400 font-mono";
        }
        liveImageOverlay.src = `/api/media/image-preview?path=${encodeURIComponent(clip.image_overlay_path)}`;
        updateLiveImageOverlayPreview();
      } else {
        currentImageOverlayServerPath = "";
        if (lblImageFileName) lblImageFileName.textContent = "Belum ada file dipilih";
        if (btnClearImage) btnClearImage.classList.add("hidden");
        imageControlsWrapper.classList.add("opacity-50", "pointer-events-none");
        if (liveImageOverlayContainer) liveImageOverlayContainer.classList.add("hidden");
        if (badgeImageOverlayStatus) {
          badgeImageOverlayStatus.textContent = "Belum Ada";
          badgeImageOverlayStatus.className = "text-[10px] text-gray-400 font-mono";
        }
      }
    }

    renderClipsGallery(currentClips);
  }

  // 10. Video Player & Custom Controls
  btnPlayPause.addEventListener("click", () => {
    if (mainVideo.paused) {
      mainVideo.play();
    } else {
      mainVideo.pause();
    }
  });

  mainVideo.addEventListener("play", () => {
    iconPlay.classList.add("hidden");
    iconPause.classList.remove("hidden");
  });

  mainVideo.addEventListener("pause", () => {
    iconPlay.classList.remove("hidden");
    iconPause.classList.add("hidden");
  });

  mainVideo.addEventListener("error", () => {
    if (selectedClip && selectedClip.staging_path) {
      const vidName = selectedClip.staging_path.split(/[\\/]/).pop();
      const fallbackUrl = `/staging/${vidName}?t=${Date.now()}`;
      if (!mainVideo.src.includes(`/staging/${vidName}`)) {
        console.warn("Video stream fallback to direct staging path:", fallbackUrl);
        mainVideo.src = fallbackUrl;
        mainVideo.load();
      }
    }
  });

  mainVideo.addEventListener("timeupdate", () => {
    if (mainVideo.duration) {
      videoScrubber.value = (mainVideo.currentTime / mainVideo.duration) * 1000;
      updateTimeLabel(mainVideo.currentTime, mainVideo.duration);
    }
  });

  videoScrubber.addEventListener("input", () => {
    if (mainVideo.duration) {
      mainVideo.currentTime = (videoScrubber.value / 1000) * mainVideo.duration;
    }
  });

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function updateTimeLabel(cur, dur) {
    timeDisplay.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;
  }

  // Volume & Persistence via localStorage (Default 40%)
  const savedVol = localStorage.getItem("clipmax_volume");
  const initialVol = savedVol !== null ? parseInt(savedVol) : 40;
  volumeSlider.value = initialVol;
  mainVideo.volume = initialVol / 100.0;
  volumeSlider.title = `Volume: ${initialVol}%`;

  volumeSlider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value);
    mainVideo.volume = val / 100.0;
    mainVideo.muted = val === 0;
    muteIcon.textContent = val === 0 ? "🔇" : "🔊";
    volumeSlider.title = `Volume: ${val}%`;
    localStorage.setItem("clipmax_volume", val);
  });

  btnMute.addEventListener("click", () => {
    if (mainVideo.muted) {
      mainVideo.muted = false;
      const vol = volumeSlider.value > 0 ? volumeSlider.value : 40;
      mainVideo.volume = vol / 100.0;
      muteIcon.textContent = "🔊";
    } else {
      mainVideo.muted = true;
      muteIcon.textContent = "🔇";
    }
  });

  // --- Description & Hook Copy Handlers ---
  function copyToClipboard(text, buttonElement) {
    if (!text) return;
    const originalHTML = buttonElement.innerHTML;
    const showSuccess = () => {
      buttonElement.innerHTML = `<span>Tersalin! ✅</span>`;
      setTimeout(() => {
        buttonElement.innerHTML = originalHTML;
      }, 1800);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(showSuccess).catch(() => {
        fallbackCopy(text, showSuccess);
      });
    } else {
      fallbackCopy(text, showSuccess);
    }
  }

  function fallbackCopy(text, callback) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      if (callback) callback();
    } catch (_) {}
    document.body.removeChild(ta);
  }

  if (btnCopyHook) {
    btnCopyHook.addEventListener("click", () => {
      if (selectedClip) copyToClipboard(selectedClip.hook || "", btnCopyHook);
    });
  }

  if (btnCopyReason) {
    btnCopyReason.addEventListener("click", () => {
      if (selectedClip) copyToClipboard(selectedClip.reasoning || "", btnCopyReason);
    });
  }

  if (btnCopyAll) {
    btnCopyAll.addEventListener("click", () => {
      if (!selectedClip) return;
      const durSec = Math.round((selectedClip.end_time || 0) - (selectedClip.start_time || 0));
      const fullText = `Judul: #${selectedClip.clip_id} ${selectedClip.title}\nViral Score: ${selectedClip.virality_score}\nHook: "${selectedClip.hook || ''}"\n\nAlasan & Deskripsi:\n${selectedClip.reasoning || ''}\n\nDurasi: ${durSec} detik`;
      copyToClipboard(fullText, btnCopyAll);
    });
  }

  // --- Video Text Overlay Live Preview & Handlers (Free Roam & WYSIWYG) ---
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function updateLiveOverlayPreview() {
    if (!liveTextOverlay || !inputOverlayText) return;
    const rawTxt = inputOverlayText.value.trim();
    if (!rawTxt) {
      liveTextOverlay.classList.add("hidden");
      return;
    }

    liveTextOverlay.classList.remove("hidden");

    // Font Family
    const font = selectOverlayFont ? selectOverlayFont.value : "Montserrat";
    liveTextOverlay.style.fontFamily = font;

    // Font Size relative to preview canvas height (WYSIWYG 1:1 with 1080x1920 video)
    const fontSize = inputRangeTextSize ? parseInt(inputRangeTextSize.value, 10) : 56;
    const canvasH = videoCanvasBox ? videoCanvasBox.clientHeight : 520;
    const previewFontSize = Math.max(10, Math.round(canvasH * (fontSize / 1920.0)));
    liveTextOverlay.style.fontSize = `${previewFontSize}px`;
    liveTextOverlay.style.lineHeight = "1.22";

    // Text Color
    let textColor = pickerOverlayTextColor ? pickerOverlayTextColor.value : "#FFFFFF";

    // Background Style
    const bgStyle = selectOverlayBgStyle ? selectOverlayBgStyle.value : "solid_black";
    liveTextOverlay.style.textShadow = "none";

    let bgColor = "#000000";
    if (bgStyle === "solid_black") {
      liveTextOverlay.style.backgroundColor = "#000000";
    } else if (bgStyle === "semi_black") {
      liveTextOverlay.style.backgroundColor = "rgba(0, 0, 0, 0.7)";
    } else if (bgStyle === "yellow_viral") {
      liveTextOverlay.style.backgroundColor = "#FFE81F";
      textColor = "#000000";
    } else if (bgStyle === "red_alert") {
      liveTextOverlay.style.backgroundColor = "#FF2A2A";
    } else if (bgStyle === "none") {
      liveTextOverlay.style.backgroundColor = "transparent";
      liveTextOverlay.style.textShadow = "2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000";
    }
    liveTextOverlay.style.color = textColor;

    // Auto-wrap matching the exact Python subtitle generator logic
    const maxChars = Math.max(14, Math.floor(1200 / fontSize));
    const lines = [];
    rawTxt.split("\n").forEach(line => {
      const trimmed = line.trim();
      if (!trimmed) return;
      if (trimmed.length > maxChars) {
        const words = trimmed.split(/\s+/);
        let cur = "";
        words.forEach(w => {
          if (!cur) cur = w;
          else if ((cur + " " + w).length <= maxChars) cur += " " + w;
          else {
            lines.push(cur);
            cur = w;
          }
        });
        if (cur) lines.push(cur);
      } else {
        lines.push(trimmed);
      }
    });

    const displayText = lines.length > 0 ? lines.join("\n") : rawTxt;
    if (liveTextContent) {
      liveTextContent.innerHTML = displayText.split("\n").map(escapeHtml).join("<br>");
    } else {
      liveTextOverlay.textContent = displayText;
    }

    // Proportional padding matching ASS Outline 8-10 (approx 0.5% of height)
    const padY = Math.max(2, Math.round(previewFontSize * 0.18));
    const padX = Math.max(4, Math.round(previewFontSize * 0.36));
    liveTextOverlay.style.padding = `${padY}px ${padX}px`;
    liveTextOverlay.style.borderRadius = "3px";

    // Free Roam Coordinates
    const xPct = inputRangeTextX ? parseFloat(inputRangeTextX.value) : 50;
    const yPct = inputRangeTextY ? parseFloat(inputRangeTextY.value) : 12;
    liveTextOverlay.style.left = `${xPct}%`;
    liveTextOverlay.style.top = `${yPct}%`;
    liveTextOverlay.style.transform = "translate(-50%, -50%)";
  }

  // Draggable Free Roam & Resizable Text Overlay
  let isDraggingText = false;
  let isResizingText = false;
  let textResizeStartY = 0;
  let textResizeStartSize = 56;

  if (liveTextOverlay && videoCanvasBox) {
    liveTextOverlay.addEventListener("pointerdown", (e) => {
      if (e.target.id === "textResizeHandle" || e.target === textResizeHandle) return;
      isDraggingText = true;
      liveTextOverlay.setPointerCapture(e.pointerId);
    });

    liveTextOverlay.addEventListener("pointermove", (e) => {
      if (!isDraggingText) return;
      const rect = videoCanvasBox.getBoundingClientRect();
      let xPct = Math.round(((e.clientX - rect.left) / rect.width) * 100);
      let yPct = Math.round(((e.clientY - rect.top) / rect.height) * 100);
      xPct = Math.max(5, Math.min(95, xPct));
      yPct = Math.max(5, Math.min(95, yPct));
      if (inputRangeTextX) inputRangeTextX.value = xPct;
      if (inputRangeTextY) inputRangeTextY.value = yPct;
      if (lblTextPosX) lblTextPosX.textContent = `${xPct}%`;
      if (lblTextPosY) lblTextPosY.textContent = `${yPct}%`;
      updateLiveOverlayPreview();
    });

    const stopTextDrag = (e) => {
      if (isDraggingText) {
        isDraggingText = false;
        try { liveTextOverlay.releasePointerCapture(e.pointerId); } catch (_) {}
      }
    };
    liveTextOverlay.addEventListener("pointerup", stopTextDrag);
    liveTextOverlay.addEventListener("pointercancel", stopTextDrag);

    // Mouse wheel resizing directly on text in preview
    liveTextOverlay.addEventListener("wheel", (e) => {
      e.preventDefault();
      let cur = inputRangeTextSize ? parseInt(inputRangeTextSize.value, 10) : 56;
      let step = e.deltaY < 0 ? 3 : -3;
      let nextVal = Math.max(28, Math.min(96, cur + step));
      if (inputRangeTextSize) inputRangeTextSize.value = nextVal;
      if (lblOverlayFontSize) lblOverlayFontSize.textContent = `${nextVal}px`;
      updateLiveOverlayPreview();
    }, { passive: false });
  }

  // Corner Resize Handle for Text in preview
  if (textResizeHandle) {
    textResizeHandle.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      isResizingText = true;
      textResizeStartY = e.clientY;
      textResizeStartSize = inputRangeTextSize ? parseInt(inputRangeTextSize.value, 10) : 56;
      textResizeHandle.setPointerCapture(e.pointerId);
    });

    textResizeHandle.addEventListener("pointermove", (e) => {
      if (!isResizingText) return;
      const deltaY = e.clientY - textResizeStartY;
      const deltaSize = Math.round(deltaY * 0.4);
      const newSize = Math.max(28, Math.min(96, textResizeStartSize + deltaSize));
      if (inputRangeTextSize) inputRangeTextSize.value = newSize;
      if (lblOverlayFontSize) lblOverlayFontSize.textContent = `${newSize}px`;
      updateLiveOverlayPreview();
    });

    const stopTextResize = (e) => {
      if (isResizingText) {
        isResizingText = false;
        try { textResizeHandle.releasePointerCapture(e.pointerId); } catch (_) {}
      }
    };
    textResizeHandle.addEventListener("pointerup", stopTextResize);
    textResizeHandle.addEventListener("pointercancel", stopTextResize);
  }

  if (inputOverlayText) {
    inputOverlayText.addEventListener("input", updateLiveOverlayPreview);
  }
  if (selectOverlayFont) {
    selectOverlayFont.addEventListener("change", updateLiveOverlayPreview);
  }
  if (pickerOverlayTextColor) {
    pickerOverlayTextColor.addEventListener("input", () => {
      if (lblOverlayTextColor) lblOverlayTextColor.textContent = pickerOverlayTextColor.value.toUpperCase();
      updateLiveOverlayPreview();
    });
  }
  if (inputRangeTextSize) {
    inputRangeTextSize.addEventListener("input", () => {
      if (lblOverlayFontSize) lblOverlayFontSize.textContent = `${inputRangeTextSize.value}px`;
      updateLiveOverlayPreview();
    });
  }
  if (selectOverlayBgStyle) {
    selectOverlayBgStyle.addEventListener("change", updateLiveOverlayPreview);
  }
  if (inputRangeTextX) {
    inputRangeTextX.addEventListener("input", () => {
      if (lblTextPosX) lblTextPosX.textContent = `${inputRangeTextX.value}%`;
      updateLiveOverlayPreview();
    });
  }
  if (inputRangeTextY) {
    inputRangeTextY.addEventListener("input", () => {
      if (lblTextPosY) lblTextPosY.textContent = `${inputRangeTextY.value}%`;
      updateLiveOverlayPreview();
    });
  }
  if (btnPosPresetTop) {
    btnPosPresetTop.addEventListener("click", () => {
      if (inputRangeTextX) inputRangeTextX.value = 50;
      if (inputRangeTextY) inputRangeTextY.value = 12;
      if (lblTextPosX) lblTextPosX.textContent = "50%";
      if (lblTextPosY) lblTextPosY.textContent = "12%";
      updateLiveOverlayPreview();
    });
  }
  if (btnPosPresetCenter) {
    btnPosPresetCenter.addEventListener("click", () => {
      if (inputRangeTextX) inputRangeTextX.value = 50;
      if (inputRangeTextY) inputRangeTextY.value = 50;
      if (lblTextPosX) lblTextPosX.textContent = "50%";
      if (lblTextPosY) lblTextPosY.textContent = "50%";
      updateLiveOverlayPreview();
    });
  }
  if (btnPosPresetBottom) {
    btnPosPresetBottom.addEventListener("click", () => {
      if (inputRangeTextX) inputRangeTextX.value = 50;
      if (inputRangeTextY) inputRangeTextY.value = 75;
      if (lblTextPosX) lblTextPosX.textContent = "50%";
      if (lblTextPosY) lblTextPosY.textContent = "75%";
      updateLiveOverlayPreview();
    });
  }

  if (btnApplyOverlay) {
    btnApplyOverlay.addEventListener("click", async () => {
      if (!selectedClip) {
        alert("Pilih klip terlebih dahulu dari galeri di sebelah kanan.");
        return;
      }
      const text = inputOverlayText.value.trim();
      if (!text) {
        alert("Harap masukkan teks video terlebih dahulu.");
        return;
      }

      btnApplyOverlay.disabled = true;
      const originalHTML = btnApplyOverlay.innerHTML;
      btnApplyOverlay.innerHTML = `<span class="animate-spin mr-1">⌛</span><span>Merender Teks...</span>`;

      const bgStyle = selectOverlayBgStyle ? selectOverlayBgStyle.value : "solid_black";
      let bgColor = "#000000";
      let hasBg = true;
      if (bgStyle === "yellow_viral") bgColor = "#FFE81F";
      else if (bgStyle === "red_alert") bgColor = "#FF2A2A";
      else if (bgStyle === "none") { bgColor = "#000000"; hasBg = false; }

      let textColor = pickerOverlayTextColor ? pickerOverlayTextColor.value : "#FFFFFF";
      if (bgStyle === "yellow_viral") textColor = "#000000";

      const xVal = inputRangeTextX ? parseFloat(inputRangeTextX.value) : 50.0;
      const yVal = inputRangeTextY ? parseFloat(inputRangeTextY.value) : 12.0;

      try {
        const resp = await fetch("/api/clips/overlay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            clip_id: selectedClip.clip_id,
            text: text,
            font_name: selectOverlayFont ? selectOverlayFont.value : "Montserrat",
            font_size: inputRangeTextSize ? parseInt(inputRangeTextSize.value, 10) : 56,
            text_color: textColor,
            bg_color: bgColor,
            has_bg: hasBg,
            position: "free",
            x_pct: xVal,
            y_pct: yVal
          })
        });

        const data = await resp.json();
        if (resp.ok) {
          if (liveTextOverlay) liveTextOverlay.classList.add("hidden");

          selectedClip.overlay_text = text;
          selectedClip.overlay_font = selectOverlayFont ? selectOverlayFont.value : "Montserrat";
          selectedClip.overlay_font_size = inputRangeTextSize ? parseInt(inputRangeTextSize.value, 10) : 56;
          selectedClip.overlay_x_pct = xVal;
          selectedClip.overlay_y_pct = yVal;
          selectedClip.overlay_text_color = textColor;
          selectedClip.overlay_bg_style = bgStyle;
          selectedClip.has_overlay = true;

          if (badgeOverlayStatus) {
            badgeOverlayStatus.textContent = "Terbakar di Video";
            badgeOverlayStatus.className = "text-[10px] text-emerald-400 font-mono";
          }

          const vidName = selectedClip.staging_path ? selectedClip.staging_path.split(/[\\/]/).pop() : "";
          mainVideo.src = `/staging/${vidName}?t=${Date.now()}`;
          mainVideo.load();
          mainVideo.play().catch(() => {});
        } else {
          alert(`Gagal merender teks: ${data.detail || "Terjadi kesalahan."}`);
        }
      } catch (err) {
        console.error("Error applying overlay:", err);
        alert(`Error merender teks: ${err.message}`);
      } finally {
        btnApplyOverlay.disabled = false;
        btnApplyOverlay.innerHTML = originalHTML;
      }
    });
  }

  if (btnRemoveOverlay) {
    btnRemoveOverlay.addEventListener("click", async () => {
      if (!selectedClip) return;
      btnRemoveOverlay.disabled = true;
      try {
        const resp = await fetch("/api/clips/remove-overlay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ clip_id: selectedClip.clip_id })
        });
        if (resp.ok) {
          if (inputOverlayText) inputOverlayText.value = "";
          selectedClip.overlay_text = "";
          selectedClip.has_overlay = false;
          if (liveTextOverlay) liveTextOverlay.classList.add("hidden");
          if (badgeOverlayStatus) {
            badgeOverlayStatus.textContent = "Live Preview";
            badgeOverlayStatus.className = "text-[10px] text-gray-400 font-mono";
          }
          const vidName = selectedClip.staging_path ? selectedClip.staging_path.split(/[\\/]/).pop() : "";
          mainVideo.src = `/staging/${vidName}?t=${Date.now()}`;
          mainVideo.load();
          mainVideo.play().catch(() => {});
        }
      } catch (err) {
        console.error("Error removing overlay:", err);
      } finally {
        btnRemoveOverlay.disabled = false;
      }
    });
  }

  // --- Image / Logo Overlay Handlers (Free Roam) ---
  function updateLiveImageOverlayPreview() {
    if (!liveImageOverlayContainer || !currentImageOverlayServerPath) {
      if (liveImageOverlayContainer) liveImageOverlayContainer.classList.add("hidden");
      return;
    }
    liveImageOverlayContainer.classList.remove("hidden");
    const scale = inputRangeImageScale ? inputRangeImageScale.value : 16;
    const opacity = inputRangeImageOpacity ? (inputRangeImageOpacity.value / 100.0) : 0.9;
    const xPct = inputRangeImageX ? inputRangeImageX.value : 85;
    const yPct = inputRangeImageY ? inputRangeImageY.value : 8;

    liveImageOverlayContainer.style.width = `${scale}%`;
    liveImageOverlayContainer.style.left = `${xPct}%`;
    liveImageOverlayContainer.style.top = `${yPct}%`;
    liveImageOverlayContainer.style.transform = "translate(-50%, -50%)";
    liveImageOverlayContainer.style.opacity = opacity;
  }

  // Draggable Free Roam & Resizable Logo / Image Overlay
  let isDraggingImage = false;
  let isResizingImage = false;
  let imgResizeStartX = 0;
  let imgResizeStartScale = 16;

  if (liveImageOverlayContainer && videoCanvasBox) {
    liveImageOverlayContainer.addEventListener("pointerdown", (e) => {
      if (e.target.id === "imageResizeHandle" || e.target === imageResizeHandle) return;
      isDraggingImage = true;
      liveImageOverlayContainer.setPointerCapture(e.pointerId);
    });
    liveImageOverlayContainer.addEventListener("pointermove", (e) => {
      if (!isDraggingImage) return;
      const rect = videoCanvasBox.getBoundingClientRect();
      let xPct = Math.round(((e.clientX - rect.left) / rect.width) * 100);
      let yPct = Math.round(((e.clientY - rect.top) / rect.height) * 100);
      xPct = Math.max(5, Math.min(95, xPct));
      yPct = Math.max(5, Math.min(95, yPct));
      if (inputRangeImageX) inputRangeImageX.value = xPct;
      if (inputRangeImageY) inputRangeImageY.value = yPct;
      if (lblImagePosX) lblImagePosX.textContent = `${xPct}%`;
      if (lblImagePosY) lblImagePosY.textContent = `${yPct}%`;
      updateLiveImageOverlayPreview();
    });
    const stopImgDrag = (e) => {
      if (isDraggingImage) {
        isDraggingImage = false;
        try { liveImageOverlayContainer.releasePointerCapture(e.pointerId); } catch (_) {}
      }
    };
    liveImageOverlayContainer.addEventListener("pointerup", stopImgDrag);
    liveImageOverlayContainer.addEventListener("pointercancel", stopImgDrag);

    // Mouse wheel resizing directly on image in preview
    liveImageOverlayContainer.addEventListener("wheel", (e) => {
      e.preventDefault();
      let cur = inputRangeImageScale ? parseInt(inputRangeImageScale.value, 10) : 16;
      let step = e.deltaY < 0 ? 1 : -1;
      let nextVal = Math.max(5, Math.min(50, cur + step));
      if (inputRangeImageScale) inputRangeImageScale.value = nextVal;
      if (lblImageScale) lblImageScale.textContent = `${nextVal}%`;
      updateLiveImageOverlayPreview();
    }, { passive: false });
  }

  // Corner Resize Handle for Image in preview
  if (imageResizeHandle) {
    imageResizeHandle.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      isResizingImage = true;
      imgResizeStartX = e.clientX;
      imgResizeStartScale = inputRangeImageScale ? parseInt(inputRangeImageScale.value, 10) : 16;
      imageResizeHandle.setPointerCapture(e.pointerId);
    });

    imageResizeHandle.addEventListener("pointermove", (e) => {
      if (!isResizingImage) return;
      const rect = videoCanvasBox.getBoundingClientRect();
      const deltaPct = Math.round(((e.clientX - imgResizeStartX) / rect.width) * 100);
      const newScale = Math.max(5, Math.min(50, imgResizeStartScale + deltaPct));
      if (inputRangeImageScale) inputRangeImageScale.value = newScale;
      if (lblImageScale) lblImageScale.textContent = `${newScale}%`;
      updateLiveImageOverlayPreview();
    });

    const stopImgResize = (e) => {
      if (isResizingImage) {
        isResizingImage = false;
        try { imageResizeHandle.releasePointerCapture(e.pointerId); } catch (_) {}
      }
    };
    imageResizeHandle.addEventListener("pointerup", stopImgResize);
    imageResizeHandle.addEventListener("pointercancel", stopImgResize);
  }

  function handleImageSelected(filePath, displayName, isNative) {
    currentImageOverlayServerPath = filePath;
    if (lblImageFileName) lblImageFileName.textContent = displayName;
    if (btnClearImage) btnClearImage.classList.remove("hidden");
    if (imageControlsWrapper) imageControlsWrapper.classList.remove("opacity-50", "pointer-events-none");

    if (liveImageOverlay) {
      if (isNative) {
        liveImageOverlay.src = `/api/media/image-preview?path=${encodeURIComponent(filePath)}`;
      }
    }
    updateLiveImageOverlayPreview();
  }

  if (btnPickImage) {
    btnPickImage.addEventListener("click", async () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_image_file) {
        try {
          let chosen = await window.pywebview.api.choose_image_file();
          if (Array.isArray(chosen)) chosen = chosen[0];
          if (chosen && typeof chosen === "string" && chosen.trim() !== "") {
            handleImageSelected(chosen.trim(), chosen.split(/[\\/]/).pop(), true);
            return;
          }
        } catch (e) {
          console.warn("pywebview choose_image_file failed, fallback to input:", e);
        }
      }
      if (fileImageInput) fileImageInput.click();
    });
  }

  if (fileImageInput) {
    fileImageInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (liveImageOverlay) {
        liveImageOverlay.src = URL.createObjectURL(file);
      }

      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await fetch("/api/clips/upload-overlay-image", {
          method: "POST",
          body: fd
        });
        const data = await res.json();
        if (res.ok && data.image_path) {
          handleImageSelected(data.image_path, file.name, false);
        } else {
          alert(`Gagal upload logo: ${data.detail || 'Terjadi kesalahan'}`);
        }
      } catch (err) {
        console.error("Upload overlay image error:", err);
      }
    });
  }

  if (btnClearImage) {
    btnClearImage.addEventListener("click", () => {
      currentImageOverlayServerPath = "";
      if (fileImageInput) fileImageInput.value = "";
      if (lblImageFileName) lblImageFileName.textContent = "Belum ada file dipilih";
      btnClearImage.classList.add("hidden");
      if (imageControlsWrapper) imageControlsWrapper.classList.add("opacity-50", "pointer-events-none");
      if (liveImageOverlayContainer) liveImageOverlayContainer.classList.add("hidden");
    });
  }

  if (inputRangeImageScale) {
    inputRangeImageScale.addEventListener("input", () => {
      if (lblImageScale) lblImageScale.textContent = `${inputRangeImageScale.value}%`;
      updateLiveImageOverlayPreview();
    });
  }
  if (inputRangeImageOpacity) {
    inputRangeImageOpacity.addEventListener("input", () => {
      if (lblImageOpacity) lblImageOpacity.textContent = `${inputRangeImageOpacity.value}%`;
      updateLiveImageOverlayPreview();
    });
  }
  if (inputRangeImageX) {
    inputRangeImageX.addEventListener("input", () => {
      if (lblImagePosX) lblImagePosX.textContent = `${inputRangeImageX.value}%`;
      updateLiveImageOverlayPreview();
    });
  }
  if (inputRangeImageY) {
    inputRangeImageY.addEventListener("input", () => {
      if (lblImagePosY) lblImagePosY.textContent = `${inputRangeImageY.value}%`;
      updateLiveImageOverlayPreview();
    });
  }

  // Logo Preset Buttons
  if (btnImgPresetTopRight) {
    btnImgPresetTopRight.addEventListener("click", () => {
      if (inputRangeImageX) inputRangeImageX.value = 85;
      if (inputRangeImageY) inputRangeImageY.value = 8;
      if (lblImagePosX) lblImagePosX.textContent = "85%";
      if (lblImagePosY) lblImagePosY.textContent = "8%";
      updateLiveImageOverlayPreview();
    });
  }
  if (btnImgPresetTopLeft) {
    btnImgPresetTopLeft.addEventListener("click", () => {
      if (inputRangeImageX) inputRangeImageX.value = 15;
      if (inputRangeImageY) inputRangeImageY.value = 8;
      if (lblImagePosX) lblImagePosX.textContent = "15%";
      if (lblImagePosY) lblImagePosY.textContent = "8%";
      updateLiveImageOverlayPreview();
    });
  }
  if (btnImgPresetBottomRight) {
    btnImgPresetBottomRight.addEventListener("click", () => {
      if (inputRangeImageX) inputRangeImageX.value = 85;
      if (inputRangeImageY) inputRangeImageY.value = 88;
      if (lblImagePosX) lblImagePosX.textContent = "85%";
      if (lblImagePosY) lblImagePosY.textContent = "88%";
      updateLiveImageOverlayPreview();
    });
  }
  if (btnImgPresetCenter) {
    btnImgPresetCenter.addEventListener("click", () => {
      if (inputRangeImageX) inputRangeImageX.value = 50;
      if (inputRangeImageY) inputRangeImageY.value = 50;
      if (lblImagePosX) lblImagePosX.textContent = "50%";
      if (lblImagePosY) lblImagePosY.textContent = "50%";
      updateLiveImageOverlayPreview();
    });
  }

  if (btnApplyImageOverlay) {
    btnApplyImageOverlay.addEventListener("click", async () => {
      if (!selectedClip) {
        alert("Pilih klip terlebih dahulu dari galeri di sebelah kanan.");
        return;
      }
      if (!currentImageOverlayServerPath) {
        alert("Pilih file logo/gambar terlebih dahulu.");
        return;
      }

      btnApplyImageOverlay.disabled = true;
      const originalHTML = btnApplyImageOverlay.innerHTML;
      btnApplyImageOverlay.innerHTML = `<span class="animate-spin mr-1">⌛</span><span>Membakar Logo...</span>`;

      const xVal = inputRangeImageX ? parseFloat(inputRangeImageX.value) : 85.0;
      const yVal = inputRangeImageY ? parseFloat(inputRangeImageY.value) : 8.0;
      const scaleVal = inputRangeImageScale ? parseFloat(inputRangeImageScale.value) : 16.0;
      const opacityVal = inputRangeImageOpacity ? (parseFloat(inputRangeImageOpacity.value) / 100.0) : 0.9;

      try {
        const resp = await fetch("/api/clips/image-overlay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            clip_id: selectedClip.clip_id,
            image_path: currentImageOverlayServerPath,
            x_pct: xVal,
            y_pct: yVal,
            scale_pct: scaleVal,
            opacity: opacityVal
          })
        });

        const data = await resp.json();
        if (resp.ok) {
          if (liveImageOverlayContainer) liveImageOverlayContainer.classList.add("hidden");

          selectedClip.image_overlay_path = currentImageOverlayServerPath;
          selectedClip.image_overlay_name = lblImageFileName ? lblImageFileName.textContent : "logo.png";
          selectedClip.image_x_pct = xVal;
          selectedClip.image_y_pct = yVal;
          selectedClip.image_scale_pct = scaleVal;
          selectedClip.image_opacity = opacityVal;
          selectedClip.has_image_overlay = true;

          if (badgeImageOverlayStatus) {
            badgeImageOverlayStatus.textContent = "Terbakar di Video";
            badgeImageOverlayStatus.className = "text-[10px] text-cyan-400 font-mono";
          }

          const vidName = selectedClip.staging_path ? selectedClip.staging_path.split(/[\\/]/).pop() : "";
          mainVideo.src = `/staging/${vidName}?t=${Date.now()}`;
          mainVideo.load();
          mainVideo.play().catch(() => {});
        } else {
          alert(`Gagal membakar logo: ${data.detail || "Terjadi kesalahan."}`);
        }
      } catch (err) {
        console.error("Error applying image overlay:", err);
        alert(`Error membakar logo: ${err.message}`);
      } finally {
        btnApplyImageOverlay.disabled = false;
        btnApplyImageOverlay.innerHTML = originalHTML;
      }
    });
  }

  if (btnRemoveImageOverlay) {
    btnRemoveImageOverlay.addEventListener("click", async () => {
      if (!selectedClip) return;
      btnRemoveImageOverlay.disabled = true;
      try {
        const resp = await fetch("/api/clips/remove-image-overlay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ clip_id: selectedClip.clip_id })
        });
        if (resp.ok) {
          selectedClip.image_overlay_path = "";
          selectedClip.has_image_overlay = false;
          if (badgeImageOverlayStatus) {
            badgeImageOverlayStatus.textContent = "Belum Ada";
            badgeImageOverlayStatus.className = "text-[10px] text-gray-400 font-mono";
          }
          const vidName = selectedClip.staging_path ? selectedClip.staging_path.split(/[\\/]/).pop() : "";
          mainVideo.src = `/staging/${vidName}?t=${Date.now()}`;
          mainVideo.load();
          mainVideo.play().catch(() => {});
        }
      } catch (err) {
        console.error("Error removing image overlay:", err);
      } finally {
        btnRemoveImageOverlay.disabled = false;
      }
    });
  }

  // 11. Export Actions
  btnExportSingle.addEventListener("click", async () => {
    if (!selectedClip) return;
    const defName = `clipmax_${selectedClip.clip_id}_${Math.round(selectedClip.start_time)}.mp4`;

    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_clip_dialog) {
      try {
        let saved = await window.pywebview.api.save_clip_dialog(selectedClip.clip_id, defName);
        if (Array.isArray(saved)) saved = saved[0];
        if (saved && typeof saved === "string" && saved.trim() !== "") {
          alert(`Klip berhasil disimpan ke:\n${saved}`);
          return;
        }
      } catch (e) {
        console.warn("Save dialog error, using direct download:", e);
      }
    }
    // Fallback: direct browser download via /api/export/{clip_id}
    const a = document.createElement("a");
    a.href = `/api/export/${selectedClip.clip_id}`;
    a.download = defName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  btnExportAll.addEventListener("click", async () => {
    if (!currentClips || currentClips.length === 0) return;

    if (window.pywebview && window.pywebview.api && window.pywebview.api.export_all_dialog) {
      try {
        let exportedDir = await window.pywebview.api.export_all_dialog();
        if (Array.isArray(exportedDir)) exportedDir = exportedDir[0];
        if (exportedDir && typeof exportedDir === "string" && exportedDir.trim() !== "") {
          alert(`Seluruh klip (${currentClips.length}) berhasil diexport ke folder:\n${exportedDir}`);
          return;
        }
      } catch (e) {
        console.warn("Export all dialog error, using direct download:", e);
      }
    }

    // Direct download trigger for each via /api/export/{clip_id}
    currentClips.forEach((c) => {
      const a = document.createElement("a");
      a.href = `/api/export/${c.clip_id}`;
      a.download = `clipmax_${c.clip_id}_${Math.round(c.start_time)}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  });

  btnNewTask.addEventListener("click", () => {
    mainVideo.pause();
    showPage("media");
  });

  // 12. Window Control Buttons
  btnMin.addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
      window.pywebview.api.minimize_window();
    }
  });

  btnClose.addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) {
      window.pywebview.api.close_window();
    } else {
      window.close();
    }
  });

  // 13. Reset Form & Clear Cache
  if (btnResetClear) {
    btnResetClear.addEventListener("click", async () => {
      inputUrl.value = "";
      inputRules.value = "";
      localVideoPath = "";
      if (boxAudioTracks) boxAudioTracks.classList.add("hidden");
      if (selectAudioTrack) selectAudioTrack.innerHTML = '<option value="default">Default / Original</option>';
      lblLocalFile.textContent = "Pilih video MP4 dari komputer...";
      localStorage.removeItem("clipmax_campaign_brief");
      localStorage.removeItem("clipmax_youtube_url");
      sessionStorage.clear();

      btnResetClear.disabled = true;
      const originalHTML = btnResetClear.innerHTML;
      btnResetClear.innerHTML = `<span class="animate-spin mr-1">⌛</span><span>Cleaning...</span>`;
      try {
        const res = await fetch("/api/cache/clear", { method: "POST" });
        const data = await res.json();
        alert(data.message || "Cache berhasil dibersihkan & form di-reset.");
      } catch (e) {
        console.warn("Gagal membersihkan cache:", e);
      } finally {
        btnResetClear.disabled = false;
        btnResetClear.innerHTML = originalHTML;
      }
    });
  }

  // 14. Reset Form Fields on Window Unload
  window.addEventListener("beforeunload", () => {
    localStorage.removeItem("clipmax_campaign_brief");
    localStorage.removeItem("clipmax_youtube_url");
    sessionStorage.clear();
  });

  // Re-scale WYSIWYG preview font size on window resize
  window.addEventListener("resize", () => {
    updateLiveOverlayPreview();
    updateLiveImageOverlayPreview();
  });

  // Initialization
  loadInitialData();
  connectWebSocket();
  showPage("home");
  loadProjectHistory();
});
