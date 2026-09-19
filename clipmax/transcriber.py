import gc
import os
import sys
import traceback
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
    device: str = "cuda",
    compute_type: str = "float16",
    language: Optional[str] = None
) -> Tuple[List[WordSegment], str]:
    from faster_whisper import WhisperModel

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    whisper_model = None
    all_words: List[WordSegment] = []
    text_segments: List[str] = []

    try:
        print(f"[ClipMax Whisper] Menginisialisasi WhisperModel('{model_size}', device='{device}', compute_type='{compute_type}')...")
        whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, info = whisper_model.transcribe(
            audio_path,
            word_timestamps=True,
            language=language
        )

        for segment in segments:
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
    except Exception as e:
        print(f"\n[ClipMax Whisper ERROR] Gagal menjalankan WhisperModel(device='{device}', compute_type='{compute_type}'): {e}", file=sys.stderr)
        traceback.print_exc()
        raise e
    finally:
        if whisper_model is not None:
            del whisper_model
        cleanup_vram()

    full_transcript = " ".join(text_segments)
    return all_words, full_transcript
