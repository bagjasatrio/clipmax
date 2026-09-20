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

  const inputEndpoint = document.getElementById("inputEndpoint");
  const inputApiKey = document.getElementById("inputApiKey");
  const selectModel = document.getElementById("selectModel");
  const btnRefreshModels = document.getElementById("btnRefreshModels");

  const inputTargetClips = document.getElementById("inputTargetClips");
  const selectDuration = document.getElementById("selectDuration");
  const selectClipMode = document.getElementById("selectClipMode");
  const inputRules = document.getElementById("inputRules");

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

  const clipsCount = document.getElementById("clipsCount");
  const clipsGallery = document.getElementById("clipsGallery");
  const btnExportSingle = document.getElementById("btnExportSingle");
  const btnExportAll = document.getElementById("btnExportAll");
  const btnNewTask = document.getElementById("btnNewTask");

  const hwPill = document.getElementById("hwPill");
  const hwPillText = document.getElementById("hwPillText");
  const btnMin = document.getElementById("btnMin");
  const btnClose = document.getElementById("btnClose");

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
      inputRules.value = cfg.campaign_rules || "";
      if (selectClipMode && cfg.clip_mode) {
        selectClipMode.value = cfg.clip_mode;
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
        clip_mode: clipModeVal
      })
    });

    // Start pipeline
    try {
      showStage("processing");
      updateProgressUI("STARTING", 5, "Mempersiapkan pipeline...");

      const res = await fetch("/api/pipeline/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_source: inputSource,
          target_clip_count: parseInt(inputTargetClips.value) || 3,
          min_duration: minD,
          max_duration: maxD,
          campaign_rules: inputRules.value.trim(),
          clip_mode: clipModeVal
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
    showStage("review");
    renderClipsGallery(clips);
    if (clips.length > 0) {
      selectClip(clips[0]);
    }
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

      // Thumbnail url
      const thumbName = clip.thumbnail_path ? clip.thumbnail_path.split(/[\\/]/).pop() : "";
      const thumbSrc = thumbName ? `/staging/${thumbName}` : "";

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
    const vidName = clip.staging_path ? clip.staging_path.split(/[\\/]/).pop() : "";
    mainVideo.src = `/staging/${vidName}`;
    mainVideo.load();
    mainVideo.play().catch(() => {});

    activeClipTitle.textContent = `#${clip.clip_id} ${clip.title}`;
    activeClipScore.textContent = `${clip.virality_score} Score`;
    activeClipHook.textContent = `"${clip.hook}"`;
    activeClipReason.textContent = clip.reasoning || "";

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

  // 11. Export Actions
  btnExportSingle.addEventListener("click", async () => {
    if (!selectedClip) return;
    const defName = `clipmax_${selectedClip.clip_id}_${Math.round(selectedClip.start_time)}.mp4`;

    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_clip_dialog) {
      try {
        const saved = await window.pywebview.api.save_clip_dialog(selectedClip.clip_id, defName);
        if (saved) {
          alert(`Klip berhasil disimpan ke:\n${saved}`);
          return;
        }
      } catch (e) {
        console.warn("Save dialog error:", e);
      }
    }
    // Fallback: direct browser download
    const vidName = selectedClip.staging_path.split(/[\\/]/).pop();
    const a = document.createElement("a");
    a.href = `/staging/${vidName}`;
    a.download = defName;
    a.click();
  });

  btnExportAll.addEventListener("click", async () => {
    if (!currentClips || currentClips.length === 0) return;

    if (window.pywebview && window.pywebview.api && window.pywebview.api.export_all_dialog) {
      try {
        const exportedDir = await window.pywebview.api.export_all_dialog();
        if (exportedDir) {
          alert(`Seluruh klip (${currentClips.length}) berhasil diexport ke folder:\n${exportedDir}`);
          return;
        }
      } catch (e) {
        console.warn("Export all dialog error:", e);
      }
    }

    // Direct download trigger for each
    currentClips.forEach((c) => {
      const vidName = c.staging_path.split(/[\\/]/).pop();
      const a = document.createElement("a");
      a.href = `/staging/${vidName}`;
      a.download = `clipmax_${c.clip_id}_${Math.round(c.start_time)}.mp4`;
      a.click();
    });
  });

  btnNewTask.addEventListener("click", () => {
    mainVideo.pause();
    showStage("standby");
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

  // Initialization
  loadInitialData();
  connectWebSocket();
});
