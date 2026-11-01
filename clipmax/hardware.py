import os
import sys
import ctypes
import platform
import subprocess
import logging
from typing import Dict, Any, List, Optional
from clipmax.config import get_ffmpeg_bin, SUBPROCESS_FLAGS, is_cuda_available

logger = logging.getLogger("clipmax.hardware")

PROFILE_POTATO = "potato"
PROFILE_MIDRANGE = "mid"
PROFILE_HIGHEND = "high"
PROFILE_AUTO = "auto"

_cached_specs: Optional[Dict[str, Any]] = None

def detect_hardware_specs(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Mendeteksi spesifikasi hardware lokal (CPU, RAM, GPU/Akselerasi, OS)
    secara presisi dan aman tanpa dependensi eksternal berat.
    Hasil di-cache di memori agar cepat (sub-millisecond).
    """
    global _cached_specs
    if _cached_specs is not None and not force_refresh:
        return _cached_specs

    os_name = platform.system()
    os_release = platform.release()
    cpu_cores = os.cpu_count() or 4

    # 1. Deteksi Kapasitas RAM Fisik
    ram_gb = 8.0
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                ram_gb = round(stat.ullTotalPhys / (1024**3), 2)
        except Exception as e:
            logger.debug(f"Gagal membaca status memori Windows: {e}")
    elif os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if "MemTotal" in line:
                        ram_gb = round(int(line.split()[1]) / (1024**2), 2)
                        break
        except Exception:
            pass

    # 2. Deteksi Encoder Hardware FFmpeg
    available_encoders: List[str] = []
    try:
        ffmpeg_bin = get_ffmpeg_bin()
        cmd = [ffmpeg_bin, "-encoders"]
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=SUBPROCESS_FLAGS,
            timeout=8
        )
        out = r.stdout or ""
        target_encoders = [
            "h264_nvenc",
            "hevc_nvenc",
            "h264_qsv",
            "h264_amf",
            "h264_videotoolbox",
            "h264_mediacodec",
            "libx264"
        ]
        for enc in target_encoders:
            if enc in out:
                available_encoders.append(enc)
    except Exception as e:
        logger.debug(f"Gagal membaca encoder FFmpeg: {e}")
        available_encoders = ["libx264"]

    has_nvenc = "h264_nvenc" in available_encoders
    has_qsv = "h264_qsv" in available_encoders
    has_amf = "h264_amf" in available_encoders
    has_apple = "h264_videotoolbox" in available_encoders
    has_mediacodec = "h264_mediacodec" in available_encoders
    cuda_active = is_cuda_available()

    # 3. Label GPU / Akselerator
    if has_nvenc:
        gpu_label = "NVIDIA GeForce (NVENC Hardware Acceleration)"
        primary_encoder = "h264_nvenc"
    elif has_apple:
        gpu_label = "Apple Silicon (VideoToolbox Hardware Acceleration)"
        primary_encoder = "h264_videotoolbox"
    elif has_qsv:
        gpu_label = "Intel QuickSync (QSV Hardware Acceleration)"
        primary_encoder = "h264_qsv"
    elif has_amf:
        gpu_label = "AMD Radeon (AMF Hardware Acceleration)"
        primary_encoder = "h264_amf"
    elif has_mediacodec:
        gpu_label = "Mobile Android (MediaCodec Hardware Acceleration)"
        primary_encoder = "h264_mediacodec"
    else:
        gpu_label = "CPU Software Encoding (libx264)"
        primary_encoder = "libx264"

    # 4. Klasifikasi Tier Otomatis (High, Mid, Potato)
    if has_nvenc or (cuda_active and ram_gb >= 12.0) or (has_apple and ram_gb >= 16.0) or (ram_gb >= 16.0 and cpu_cores >= 8):
        detected_tier = PROFILE_HIGHEND
        tier_title = "High-End Studio"
        badge_color = "emerald"
    elif has_qsv or has_amf or (ram_gb >= 6.0 and cpu_cores >= 4):
        detected_tier = PROFILE_MIDRANGE
        tier_title = "Mid-Range Balanced"
        badge_color = "amber"
    else:
        detected_tier = PROFILE_POTATO
        tier_title = "Potato Mode (Hemat Daya & Ringan)"
        badge_color = "yellow"

    _cached_specs = {
        "os": f"{os_name} {os_release}",
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "cuda_available": cuda_active,
        "has_nvenc": has_nvenc,
        "has_qsv": has_qsv,
        "has_amf": has_amf,
        "has_apple": has_apple,
        "has_mediacodec": has_mediacodec,
        "primary_encoder": primary_encoder,
        "available_encoders": available_encoders,
        "gpu_label": gpu_label,
        "detected_tier": detected_tier,
        "tier_title": tier_title,
        "badge_color": badge_color,
    }
    return _cached_specs

def get_profile_tuning(tier: str, specs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Mengembalikan parameter tuning optimal berdasarkan tier yang dipilih.
    """
    specs = specs or detect_hardware_specs()
    t = tier.lower()

    if t == PROFILE_POTATO:
        cpu_cores = specs.get("cpu_cores", 4)
        thread_cap = max(1, cpu_cores - 1)
        return {
            "tier": PROFILE_POTATO,
            "tier_title": "Potato Mode (Hemat Daya & Ringan)",
            "whisper_model": "tiny",
            "device": "cpu",
            "compute_type": "int8",
            "primary_encoder": "libx264",
            "encoder_preset": "ultrafast",
            "crf": 23,
            "video_bitrate": "3.5M",
            "reframe_sample_step": 45,       # Deteksi tiap ~1.5 detik sekali (sangat hemat CPU)
            "reframe_detect_width": 360,      # Frame di-downscale ke 360p sebelum deteksi wajah
            "cpu_thread_limit": thread_cap,   # Batasi thread agar PC/HP tidak freeze
            "preview_resolution": "480p",
            "description": "Dioptimalkan untuk laptop kentang, PC tanpa GPU diskrit, dan smartphone baterai hemat."
        }
    elif t == PROFILE_MIDRANGE:
        enc = specs.get("primary_encoder", "libx264")
        preset = "p4" if enc == "h264_nvenc" else ("fast" if enc == "libx264" else "default")
        use_cuda = specs.get("cuda_available", False)
        return {
            "tier": PROFILE_MIDRANGE,
            "tier_title": "Mid-Range Balanced",
            "whisper_model": "base",
            "device": "cuda" if use_cuda else "cpu",
            "compute_type": "int8",
            "primary_encoder": enc,
            "encoder_preset": preset,
            "crf": 20,
            "video_bitrate": "5M",
            "reframe_sample_step": 20,       # Deteksi tiap ~0.66 detik sekali
            "reframe_detect_width": 480,      # Frame di-downscale ke 480p
            "cpu_thread_limit": 0,            # Default OS scheduling
            "preview_resolution": "720p",
            "description": "Keseimbangan kecepatan render dan kualitas visual untuk laptop kantor & PC i5/Ryzen 5."
        }
    else:  # High-End Studio
        has_nv = specs.get("has_nvenc", False)
        enc = "h264_nvenc" if has_nv else specs.get("primary_encoder", "libx264")
        preset = "p6" if enc == "h264_nvenc" else "veryfast"
        use_cuda = specs.get("cuda_available", False)
        vram_large = specs.get("ram_gb", 8.0) >= 16.0
        return {
            "tier": PROFILE_HIGHEND,
            "tier_title": "High-End Studio (RTX/CUDA)",
            "whisper_model": "small" if vram_large else "base",
            "device": "cuda" if use_cuda else "cpu",
            "compute_type": "float16" if use_cuda else "int8",
            "primary_encoder": enc,
            "encoder_preset": preset,
            "crf": 18,
            "video_bitrate": "6M",
            "reframe_sample_step": 10,       # Deteksi halus tiap ~0.33 detik sekali
            "reframe_detect_width": 640,      # Frame deteksi detail 640p
            "cpu_thread_limit": 0,
            "preview_resolution": "1080p",
            "description": "Performa maksimal grafis RTX dan multi-core. Render instan NVENC p6 dan transkripsi cepat."
        }

def tune_config_for_hardware(config: Any, profile_override: str = "auto") -> Dict[str, Any]:
    """
    Menyelaraskan objek AppConfig dengan profil hardware yang ditargetkan.
    Jika profile_override == 'auto', menggunakan klasifikasi otomatis perangkat.
    """
    specs = detect_hardware_specs()
    chosen_tier = specs["detected_tier"] if (profile_override == PROFILE_AUTO or not profile_override) else profile_override
    tuning = get_profile_tuning(chosen_tier, specs)

    # Terapkan tuning ke config
    config.hardware_profile = profile_override
    config.whisper_model = tuning["whisper_model"]
    config.device = tuning["device"]
    config.compute_type = tuning["compute_type"]
    config.nvenc_preset = tuning["encoder_preset"]
    config.video_bitrate = tuning["video_bitrate"]
    
    if hasattr(config, "reframe_sample_step"):
        config.reframe_sample_step = tuning["reframe_sample_step"]
    if hasattr(config, "reframe_detect_width"):
        config.reframe_detect_width = tuning["reframe_detect_width"]
    if hasattr(config, "cpu_thread_limit"):
        config.cpu_thread_limit = tuning["cpu_thread_limit"]

    logger.info(
        f"ClipMax Hardware Profile disetel ke: [{tuning['tier_title']}] "
        f"(Encoder: {tuning['primary_encoder']}, Preset: {tuning['encoder_preset']}, Whisper: {tuning['whisper_model']})"
    )

    return {
        "applied_profile": profile_override,
        "active_tier": chosen_tier,
        "tuning": tuning,
        "specs": specs,
    }
