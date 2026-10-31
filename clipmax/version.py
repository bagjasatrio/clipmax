"""
ClipMax Studio Pro - Version & Update Log Registry
Proprietary Commercial Software. All rights reserved.
"""

from typing import List, Dict, Any

__version__ = "2.6.0"
APP_NAME = "ClipMax Studio Pro"
EDITION = "Commercial Enterprise"
COPYRIGHT = "© 2026 ClipMax Studio Pro. All rights reserved."

CHANGELOG: List[Dict[str, Any]] = [
    {
        "version": "2.6.0",
        "date": "2026-11-01",
        "title": "CapCut Multitrack NLE Suite & Universal Social Publisher",
        "badge": "Terbaru",
        "changes": [
            "Timeline Multitrack Terpartisi: Klip video AI, trek subtitle, dan audio ditampilkan terpotong-potong per segmen klip secara non-linear (NLE) ala CapCut.",
            "Publish Semua Klip Medsos: Fitur antrian publikasi massal ke YouTube Shorts & TikTok dalam satu kali klik tanpa perlu satu persatu.",
            "Perbaikan OAuth YouTube: Validasi token refresh realtime, penanganan otomatis invalid/expired token dengan tombol login ulang instan.",
            "Silent Subprocess Execution: Pemotongan & render video berjalan 100% tanpa pop-up terminal/console eksternal.",
            "Palet Warna Emerald Green & Warm Butter Yellow: Tampilan visual ramah di mata dengan kontras profesional.",
            "Transisi Lisensi Komersial: Sistem registrasi versi dan log pembaruan terpadu untuk platform SaaS."
        ]
    },
    {
        "version": "2.5.0",
        "date": "2026-10-31",
        "title": "CapCut Desktop Suite Redesign & Precision Export Trimming",
        "badge": "Major UI",
        "changes": [
            "Redesain Beranda CapCut Desktop: Hero banner '+ Buat Proyek Baru' dan kartu shortcut AI Creative Suite.",
            "Multitrack Editor Workspace: Asset bin kiri, monitor player 9:16 tengah, inspector kanan, dan timeline bawah.",
            "Interactive In/Out Trimming: Pemangkasan titik awal & akhir klip langsung dieksekusi via NVENC saat export.",
            "Filter & Pencarian Galeri Klip: Quick filter berdasarkan skor viralitas dan durasi."
        ]
    },
    {
        "version": "2.4.0",
        "date": "2026-10-28",
        "title": "Viral Subtitle Presets & Social Captions",
        "badge": "AI & Subtitle",
        "changes": [
            "7 Subtitle Presets: Hormozi Pop, Cyber Yellow, Clean White, Neon Mint, dll.",
            "Multi-format Metadata: Otomatis hasilkan YouTube Chapters, Markdown Summary, dan Social Captions dengan Hook.",
            "Ekspor Langsung SRT: Dukungan ekspor subtitle SRT per klip."
        ]
    },
    {
        "version": "2.0.0",
        "date": "2026-10-20",
        "title": "NVIDIA NVENC Hardware Acceleration & Faster-Whisper",
        "badge": "Engine",
        "changes": [
            "Akselerasi GPU NVENC preset p6 pada kartu NVIDIA GeForce RTX.",
            "Transkripsi audio lokal berkecepatan tinggi dengan Faster-Whisper CUDA.",
            "MediaPipe Face Tracking untuk auto-reframe rasio vertikal 9:16."
        ]
    }
]
