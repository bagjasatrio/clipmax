import gc
import os
import sys
from typing import List, Tuple, Optional
from pydantic import BaseModel
import torch
from clipmax.dll_setup import setup_cuda_dll_paths

# Setup CUDA DLL search paths immediately before loading faster_whisper / ctranslate2
setup_cuda_dll_paths()

class WordSegment(BaseModel):
    word: str
    start: float
    end: float
    probability: float

def cleanup_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        except Exception:
            pass

def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    language: Optional[str] = None
) -> Tuple[List[WordSegment], str]:
    from faster_whisper import WhisperModel

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if device is None:
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cuda" if torch.cuda.is_available() else "cpu"

    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"

    whisper_model = None
    all_words: List[WordSegment] = []
    text_segments: List[str] = []

    try:
        # Attempt primary initialization
        try:
            whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
            segments, info = whisper_model.transcribe(
                audio_path,
                word_timestamps=True,
                language=language
            )
            # Evaluate generator to catch lazy CUDA initialization errors (e.g. cublas64_12.dll not found)
            segments_list = []
            for seg in segments:
                segments_list.append(seg)
        except Exception as e:
            if device == "cuda":
                print(f"[ClipMax Warning] CUDA initialization/execution gagal: {e}. Mengalihkan otomatis ke fallback CPU (int8)...")
                if whisper_model is not None:
                    del whisper_model
                    whisper_model = None
                cleanup_vram()
                device = "cpu"
                compute_type = "int8"
                whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                segments, info = whisper_model.transcribe(
                    audio_path,
                    word_timestamps=True,
                    language=language
                )
                segments_list = list(segments)
            else:
                raise e

        for segment in segments_list:
            text_segments.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    clean_w = w.word.strip()
                    if clean_w:
                        all_words.append(
                            WordSegment(
                                word=clean_w,
                                start=float(w.start),
                                end=float(w.end),
                                probability=float(w.probability)
                            )
                        )
    finally:
        if whisper_model is not None:
            del whisper_model
        cleanup_vram()

    full_transcript = " ".join(text_segments)
    return all_words, full_transcript
