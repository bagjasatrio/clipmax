# Product Requirement Document (PRD) v2.4 (Production & Distribution Hardened)
## Project: ClipMax (Autonomous Desktop AI Video Clipper)

---

### 1. Executive Summary & Vision
ClipMax adalah aplikasi desktop mandiri untuk mengotomatisasi konversi video panjang (podcast, webinar, wawancara) berformat 16:9 menjadi video vertikal pendek (TikTok/Reels/Shorts) berformat 9:16 [cite: 5, 6].
Sistem beroperasi dengan arsitektur **Hybrid**:
- **Lokal (Offline):** Ekstraksi audio, transkripsi presisi per kata, deteksi wajah & active speaker, penanganan multi-speaker, auto-fallback CPU/CUDA, pengelolaan alokasi VRAM secara ketat, dan hardware-accelerated video rendering via GPU NVENC [cite: 6].
- **Dynamic AI Provider Gateway:** Kurasi konten semantik, penilaian viralitas, dan perancangan hook berbasis OpenAI-compatible API modular (9Router, Axet Proxy, Hermes, Ollama, OpenRouter, Groq, atau OpenAI langsung) dengan fitur **Auto-Discover Models** dan parser waktu/JSON universal [cite: 6].

---

### 2. Target Hardware & Runtime Environment
- **OS:** Windows 10/11 x64 [cite: 6]
- **Primary Target Spec:** AMD Ryzen 7 4800H (8 Cores, 16 Threads), NVIDIA GeForce RTX 3050 Laptop GPU (4 GB GDDR6 VRAM, NVENC Gen 6), 24 GB DDR4 RAM [cite: 6]
- **Portability & Porting Target:** Kompatibel untuk perangkat tanpa NVIDIA GPU melalui fallback CPU murni (`device='cpu', compute_type='int8'`) [cite: 6].
- **Python Runtime:** Python 3.10 atau 3.11 [cite: 6]
- **Driver / Compute:** NVIDIA CUDA Toolkit 12.x, cuDNN 9.x, FFmpeg dengan dukungan NVENC [cite: 6].

---

### 3. Dynamic Custom Provider & Model Discovery Specification

Antarmuka pengaturan menerapkan sistem endpoint modular [cite: 6]:

#### 3.1 Form Entri Custom Endpoint (UI Component)
Pengguna dapat menambahkan dan memilih profil provider dengan atribut [cite: 6]:
- **Provider Name:** Label identitas (contoh: "9Router Local", "Axet Proxy", "Ollama", "OpenRouter") [cite: 6].
- **Endpoint URL:** Base URL OpenAI-compatible (contoh: `http://localhost:20128/v1`, `http://127.0.0.1:8081/v1`, `https://openrouter.ai/api/v1`) [cite: 6].
- **API Key:** Opsional (bisa dikosongkan untuk proxy lokal tanpa auth) [cite: 6].
- **Discover Models Toggle / Button:** Opsi untuk mengambil daftar model aktif secara instan [cite: 6].
- **Model Selector:** Dropdown dinamis berisi model yang terdeteksi dari endpoint [cite: 6].

#### 3.2 Alur Auto-Discovery Model (`GET /v1/models`)
1. Request ke endpoint saat user klik tombol test/discover [cite: 6]:
   ```http
   GET {endpoint_url}/models
   Headers:
     Authorization: Bearer {api_key} (jika diisi)
   ```
2. Parsing respon standar OpenAI array `data[*].id` ke dropdown UI [cite: 6].
3. Simpan konfigurasi aktif ke `config.json` lokal [cite: 6].

---

### 4. Technical Specifications, Hardening & Memory Lifecycle

#### 4.1 Dependency Manifest (`requirements.txt`)
```text
torch>=2.2.0 --index-url https://download.pytorch.org/whl/cu121
torchvision>=0.17.0 --index-url https://download.pytorch.org/whl/cu121
torchaudio>=2.2.0 --index-url https://download.pytorch.org/whl/cu121
faster-whisper>=1.0.0
nvidia-cublas-cu12
nvidia-cudnn-cu12
mediapipe>=0.10.9
opencv-python>=4.8.0
openai>=1.12.0
pydantic>=2.5.0
requests>=2.31.0
python-dotenv>=1.0.0
```

#### 4.2 Strict Sequential VRAM Garbage Collection (Anti-OOM 4GB)
Mengingat VRAM GPU sebesar 4GB sangat terbatas, model deep learning tidak boleh ditahan di memori secara simultan [cite: 6]:
- Begitu Stage 2 (Transkripsi) selesai, wajib jalankan pembersihan memori [cite: 6]:
  ```python
  import gc, torch
  del whisper_model
  gc.collect()
  if torch.cuda.is_available():
      torch.cuda.empty_cache()
  ```
- Rendering FFmpeg NVENC dan inferensi MediaPipe dijalankan setelah memori CUDA benar-benar bersih [cite: 6].

#### 4.3 Bundled Static Binaries & Fallback Device Detection
- **Bundled FFmpeg:** Jangan andalkan variabel PATH sistem pengguna [cite: 6]. Aplikasi mendistribusikan static binary FFmpeg di dalam direktori internal `./bin/ffmpeg.exe` dan `./bin/ffprobe.exe` [cite: 6].
- **Hardware Fallback:**
  ```python
  import torch
  compute_device = "cuda" if torch.cuda.is_available() else "cpu"
  compute_type = "float16" if compute_device == "cuda" else "int8"
  ```

#### 4.4 Universal Time Parsing & Resilient JSON
- Tangani ketidakkonsistenan respon format waktu LLM (`"00:01:23"`, `"01:23"`, atau float murni `83.5`) [cite: 6]:
  ```python
  def parse_to_seconds(val) -> float:
      if isinstance(val, (int, float)):
          return float(val)
      if isinstance(val, str):
          parts = val.strip().split(":")
          if len(parts) == 3:
              return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
          if len(parts) == 2:
              return float(parts[0]) * 60 + float(parts[1])
          return float(val)
      return 0.0
  ```
- **Fallback Regex Parser:** Ekstrak JSON via blok ```json ... ``` atau kurung kurawal pertama jika provider menolak parameter `response_format={"type": "json_object"}` [cite: 6].

#### 4.5 Windows-Safe FFmpeg Path Escaping
- Path file subtitle `.ass` wajib dinormalisasi [cite: 6]:
  ```python
  def sanitize_ffmpeg_path(raw_path: str) -> str:
      clean = raw_path.replace("\", "/")
      if len(clean) > 1 and clean[1] == ":":
          clean = clean[0] + "\:" + clean[2:]
      return clean
  ```

---

### 5. Detailed Execution Flow (Algorithmic Logic)

#### Stage 1: Audio Extraction
- Ekstrak track audio mono 16kHz via FFmpeg lokal [cite: 6]:
  `{bundled_ffmpeg} -y -i "{input_video}" -vn -acodec pcm_s16le -ar 16000 -ac 1 "{temp_audio.wav}"`

#### Stage 2: Word-Level Transcription (Lokal GPU / CPU Fallback)
1. Eksekusi `faster_whisper.WhisperModel("small", device=compute_device, compute_type=compute_type)` [cite: 6].
2. Ambil data dengan `word_timestamps=True` [cite: 6].
3. Simpan data kata di memori, buat teks kalimat ringkas untuk prompt LLM [cite: 6].
4. **Trigger VRAM Garbage Collection** (Hapus objek model Whisper dari CUDA) [cite: 6].

#### Stage 3: LLM Virality Evaluation (Dynamic Endpoint)
1. Kirim teks ringkas ke `{endpoint_url}/chat/completions` [cite: 6].
2. Ekstrak data via `safe_json_parse` [cite: 6].
3. Validasi `start_time` dan `end_time` menggunakan `parse_to_seconds` [cite: 6].

#### Stage 4: Dynamic Auto-Reframe (9:16 Smooth Crop)
1. Jalankan MediaPipe pada klip terpilih [cite: 6].
2. **Kasus 1 Wajah:** Hitung $X_{center}$, haluskan dengan EMA ($lpha = 0.15$) [cite: 6].
3. **Kasus Multi-Wajah:** Analisis bukaan bibir (*active speaker*) atau terapkan layout otomatis **Split-Screen Top-Bottom** (1080x960 per pembicara) [cite: 6].

#### Stage 5: Kinetic Dynamic ASS Subtitle Styling
1. Filter kata-kata Whisper pada rentang `start_time` hingga `end_time` [cite: 6].
2. Tulis file `.ass` dengan font tebal, outline stroke hitam 3px, dan warna highlight aktif (kuning/hijau) [cite: 6].

#### Stage 6: Hardware-Accelerated Video Rendering
1. Amankan path file ASS menggunakan `sanitize_ffmpeg_path` [cite: 6].
2. Tentukan video encoder: `h264_nvenc` jika GPU tersedia, atau `libx264` jika fallback ke CPU [cite: 6].
3. Jalankan rendering [cite: 6]:
   ```bash
   {bundled_ffmpeg} -y -ss {start_time} -to {end_time} -i "{input_video}"      -vf "crop=ih*(9/16):ih:{crop_x}:0,scale=1080:1920,subtitles='{escaped_ass_path}'"      -c:v {video_encoder} -preset p4 -b:v 6000k      -c:a aac -b:a 192k      "{output_dir}/clip_{clip_id}.mp4"
   ```

---

### 6. Desktop Integration, Task Lifecycle & Cancellation Specification

Backend desktop (FastAPI/Sidecar atau PySide Worker) wajib mengimplementasikan manajemen thread dan pembatalan tugas [cite: 6]:

#### 6.1 Process Tracking & Graceful Cancellation Token
- Setiap antrean proses merekam `active_process_id` (PID FFmpeg) dan flag pembatalan `threading.Event(cancel_requested)` [cite: 6].
- Jika pengguna menekan tombol **"Batal / Stop"** di UI [cite: 6]:
  1. Backend memicu `cancel_requested.set()` [cite: 6].
  2. Subproses FFmpeg yang berjalan langsung dihentikan paksa via `process.kill()` atau `taskkill /F /PID {pid}` [cite: 6].
  3. Lakukan pembersihan file temporary (`temp_audio.wav`, `temp_clip.ass`) [cite: 6].
  4. Bersihkan VRAM (`torch.cuda.empty_cache()`) [cite: 6].
  5. Kirim event status `CANCELLED` ke antarmuka pengguna [cite: 6].

#### 6.2 State & Progress Reporting
- Backend mengekspos event progress [cite: 6]:
  `IDLE` -> `EXTRACTING_AUDIO (10%)` -> `TRANSCRIBING (30%)` -> `AI_EVALUATING (50%)` -> `TRACKING_FACES (70%)` -> `RENDERING (90%)` -> `COMPLETED (100%)` [cite: 6].

---

### 7. Definition of Done (DoD)
1. Antarmuka pengaturan memiliki form custom endpoint (Name, URL, API Key, Discover Models, Test button) [cite: 6].
2. Fitur "Discover Models" berhasil menarik daftar model aktif via `GET {url}/models` dan mengisi dropdown secara dinamis [cite: 6].
3. Pengujian pada video panjang tidak memicu error `CUDA Out of Memory (OOM)` karena garbage collection VRAM berjalan optimal [cite: 6].
4. Fitur pembatalan (*cancel process*) berhasil menghentikan proses FFmpeg dan menghapus file sampah tanpa membuat UI macet [cite: 6].
5. Nilai `start_time` dan `end_time` baik dalam detik maupun format `HH:MM:SS` terkonversi tepat tanpa menghasilkan klip durasi 0 detik [cite: 6].
6. Aplikasi ClipMax tetap dapat dijalankan secara fallback di laptop tanpa GPU diskret (CPU mode).
7. Video hasil klip 9:16 terpotong rapi dengan subtitle kinetik yang sinkron dan wajah selalu berada di frame [cite: 6].
