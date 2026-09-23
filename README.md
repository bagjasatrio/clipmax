# 🎬 ClipMax — Autonomous Desktop AI Video Clipper

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Hardware Acceleration](https://img.shields.io/badge/Render-NVIDIA%20NVENC%20(p6)-green.svg)](https://developer.nvidia.com/nvidia-video-codec-sdk)
[![AI Engine](https://img.shields.io/badge/Transcription-Faster--Whisper%20CUDA-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Quality](https://img.shields.io/badge/Output-Full%20HD%201080x1920-red.svg)](https://ffmpeg.org)
[![Test Suite](https://img.shields.io/badge/Tests-85%2F85%20Passing-brightgreen.svg)](#testing)

**ClipMax** adalah aplikasi desktop mandiri berbasis AI untuk mengonversi video panjang horizontal (16:9) seperti podcast, gameplay, livestream, dan webinar menjadi video pendek vertikal (9:16 Full HD 1080x1920) yang siap diunggah ke TikTok, Instagram Reels, dan YouTube Shorts secara otomatis.

Dirancang khusus untuk performa tinggi pada perangkat dengan GPU konsumen (target: **NVIDIA GeForce RTX 3050 Laptop GPU 4GB VRAM**), ClipMax memanfaatkan hardware acceleration murni, manajemen memori VRAM yang ketat, dan integrasi LLM fleksibel.

---

## ✨ Fitur Unggulan

### 1. Ingestion Bersih & Cepat
- **YouTube Ingestion Mandiri:** Menggunakan **Invidious API publik** sebagai engine utama untuk direct stream download tanpa memerlukan cookies atau akun Google.
- **yt-dlp Fallback:** Dilengkapi fallback cerdas ke yt-dlp jika instance Invidious sedang sibuk.
- **Local Video Import:** Mendukung import file lokal (`.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`) dengan native file dialog dan drag-and-drop.

### 2. Transkripsi Presisi (Faster-Whisper CUDA)
- Transkripsi tingkat kata (*word-level timestamps*) dengan akurasi tinggi menggunakan model multilingual `small` pada GPU CUDA `float16`.
- Dilengkapi **Whisper Initial Prompt** khusus istilah gaming, slang, dan Indoglish (Mobile Legends, war, lord, wipeout, ulti, flicker, dll.).
- **Automatic Subtitle Polisher via LLM:** Koreksi otomatis typo fonetik dan ejaan percakapan tanpa menggeser stempel waktu kata.

### 3. Kurasi AI Cerdas (OpenAI-Compatible & Gemini via Proxy)
- **Universal Provider Gateway:** Kompatibel dengan semua endpoint OpenAI-compatible (`9Router`, `Axet Proxy`, `Ollama`, `OpenRouter`, `Groq`, OpenAI).
- **Auto-Discovery Models:** Mengambil daftar model aktif secara langsung dari endpoint melalui `GET /v1/models`.
- **Mode Klip Ganda:**
  - **Single Clip Mode (Default):** Memotong segmen momen puncak tunggal dengan hook viral kuat.
  - **Multi-Cut Montage Mode:** Mengidentifikasi beberapa momen kunci (misal: First Blood, Lord Steal, Final Push) dan menggabungkannya via FFmpeg concat demuxer menjadi satu video utuh.
- **Recency Bias & Reverse Anchor Timing:** Logika hitung mundur dari momen kemenangan/selebrasi akhir untuk menjamin syarat ending terpenuhi tanpa terpotong.

### 4. Smart Auto-Reframe 9:16 Full HD
- **MediaPipe Face Detection & Tracking:** Pelacakan wajah pembicara aktif secara dinamis.
- **Scene Detection (PySceneDetect):** Segmentasi adegan visual untuk transisi kamera yang mulus.
- **Full HD 1080x1920 Lanczos Scaler:** Output vertikal tajam tanpa blur pecah, dipadukan background blur halus `boxblur=20:20`.

### 5. Kinetic Karaoke Subtitles & Custom Styling
- Subtitle ASS dinamis dengan animasi highlight kata per kata saat diucapkan.
- Format warna BGR ASS presisi (`&H00BBGGRR&`).
- Kustomisasi warna Base (teks biasa) dan Highlight (kata aktif) dengan preset instan (*Merah-Putih, Kuning TikTok, Hijau Neon, Cyan Gamer, Custom*).

### 6. Video Text Overlay (Judul / Hook Callout)
- Tambahkan teks judul/hook langsung di pemutar video preview 9:16.
- **Pilihan Font:** Montserrat, Impact, Roboto, Arial, Trebuchet MS, Georgia.
- **Pilihan Background Box:** Box Hitam Solid, Box Hitam 60%, Box Kuning Viral, Box Merah Alert, atau Tanpa Background (Outline Glow).
- **Live Real-Time Preview:** Pratinjau DOM visual langsung di atas pemutar video sebelum dirender.
- **Fast NVENC Re-Rendering:** Membakar teks permanen ke video dalam 1-2 detik tanpa render ulang dari awal.

### 7. Hardware Rendering NVENC & Manajemen VRAM
- Rendering via FFmpeg **NVIDIA NVENC (`h264_nvenc`)** dengan preset `p6`, `-tune hq`, `-rc vbr`, `-cq 19`, `-b:v 6M`, `-maxrate 10M`, `-bufsize 12M`, dan AAC 192k audio.
- **Pembersihan VRAM Ketat (Anti-OOM 4GB):** Model Whisper segera dibongkar (`del model`, `gc.collect()`, `torch.cuda.empty_cache()`) sebelum FFmpeg NVENC dan MediaPipe berjalan.
- **Frame-Accurate Seeking:** Mencegah drift potongan video dengan memposisikan `-ss` sebelum `-i` dan `-to` durasi setelah `-i`.

### 8. Antarmuka Desktop Modern (PyWebView & PySide6)
- **Antarmuka Utama:** Web-based desktop app via **PyWebView** dengan tema OLED dark modern (Tailwind CSS).
- **Antarmuka Alternatif:** Native Qt GUI via **PySide6** (`python run.py --pyside`).
- **Auto-Clear Cache:** Pembersihan otomatis folder cache temporary saat aplikasi dibuka dan ditutup, serta tombol manual *Reset & Clear Cache*.

---

## 🛠️ Arsitektur Pipeline

```
[ Input: YouTube / Local MP4 ]
            │
            ▼
[ Stage 1: Ingestion & Audio Extraction (16kHz PCM WAV) ]
            │
            ▼
[ Stage 2: Faster-Whisper CUDA Transcription (Word-Level Timestamps) ]
            │  └─> [ VRAM Memory Cleanup: Anti-OOM 4GB ]
            ▼
[ Stage 3: LLM Curation Gateway (Gemini/OpenAI Auto-Discovery) ]
            │  └─> Single Clip OR Multi-Cut Montage Plan
            ▼
[ Stage 4: Visual Analysis & 9:16 Reframe (MediaPipe + PySceneDetect) ]
            │
            ▼
[ Stage 5: Subtitle Generation (Dynamic Karaoke ASS + Custom Colors) ]
            │
            ▼
[ Stage 6: High-Quality Hardware Rendering (FFmpeg NVENC p6 1080x1920) ]
            │
            ▼
[ Review Workspace: Live Video Text Overlay & Multi-Clip Gallery Export ]
```

---

## 💻 Kebutuhan Sistem

- **Sistem Operasi:** Windows 10/11 64-bit
- **Prosesor:** Minimal 4 Cores (Direkomendasikan: AMD Ryzen 5/7 atau Intel Core i5/i7)
- **RAM:** Minimal 16 GB (Direkomendasikan: 24 GB)
- **GPU:** NVIDIA GeForce GTX 1650 / RTX 3050 ke atas (VRAM minimal 4 GB) dengan driver NVIDIA terbaru
- **CUDA:** NVIDIA CUDA Toolkit 12.x & cuDNN 9.x
- **Python:** Python 3.10 – 3.12 (64-bit)

---

## 🚀 Panduan Instalasi & Menjalankan

### 1. Clone Repositori
```bash
git clone https://github.com/bagjasatrio/clipmax.git
cd clipmax
```

### 2. Siapkan Virtual Environment
```bash
python -m venv .venv
# Aktifkan virtual environment di Windows:
.venv\Scripts\activate
```

### 3. Install Dependensi
```bash
# Install PyTorch dengan CUDA 12.1:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install pustaka lainnya:
pip install -r requirements.txt
```

### 4. Pastikan Binari FFmpeg
Letakkan file binari `ffmpeg.exe` dan `ffprobe.exe` berdukungan NVENC ke dalam folder `bin/`:
```text
clipmax/
├── bin/
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   ├── face_landmarker.task
│   └── face_detection_yunet_2023mar.onnx
```

### 5. Jalankan Aplikasi
```bash
# Mode Utama (Modern PyWebView Desktop App):
python run.py

# Atau Mode Alternatif (Native PySide6 Qt App):
python run.py --pyside
```

---

## 🧪 Pengujian (Testing)

Semua komponen inti telah diuji secara menyeluruh melalui test suite `pytest`:
```bash
pytest
```
*Hasil Verifikasi:* **85/85 tests passed** mencakup pengujian:
- AI Gateway & Montage Schema Parsing
- Invidious API & YouTube URL Extractor
- Whisper CUDA Audio & Gaming Prompts
- ASS Subtitle Generator & Karaoke Inline BGR Color Tags
- MediaPipe Face Reframe & PySceneDetect
- Frame-Accurate Seeking FFmpeg Renderer
- Video Text Overlay & Fast Re-render API Endpoints
- Web Server REST APIs & Desktop JS Bridge

---

## 📂 Struktur Proyek

```text
clipmax/
├── bin/                       # Model MediaPipe, face landmarkers, dan binari FFmpeg
├── clipmax/
│   ├── ai_gateway.py          # LLM Curation, scoring viralitas, anchor timing & montage
│   ├── audio.py               # Ekstraksi audio WAV 16kHz via FFmpeg
│   ├── config.py              # Konfigurasi aplikasi, GPU detection & cache management
│   ├── dll_setup.py           # Injeksi path CUDA DLL untuk Windows
│   ├── downloader.py          # Invidious API public instance stream & yt-dlp fallback
│   ├── pipeline.py            # Orchestrator utama pemrosesan klip 6 tahap
│   ├── reframe.py             # MediaPipe face tracking & PySceneDetect visual reframe
│   ├── renderer.py            # NVENC p6 1080x1920 rendering & text overlay burning
│   ├── subtitle.py            # Generator ASS karaoke dinamis & overlay text ASS
│   ├── subtitle_cleaner.py    # Auto-polisher transkrip percakapan via LLM
│   ├── transcriber.py         # Faster-Whisper CUDA float16 dengan VRAM GC cleanup
│   ├── ui/                    # Antarmuka desktop native PySide6 (Qt)
│   └── web/                   # Backend FastAPI & frontend Tailwind CSS PyWebView
├── tests/                     # 85 automated unit & integration tests
├── desktop_app.py             # Launcher aplikasi PyWebView & bridge dialog Windows
├── run.py                     # Entry point utama aplikasi desktop
└── requirements.txt           # Daftar pustaka Python yang dibutuhkan
```

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).
