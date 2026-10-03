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

class TranscriptionResult(tuple):
    def __new__(cls, words: List[WordSegment], text: str, language: str = "id"):
        return super().__new__(cls, (words, text))

    def __init__(self, words: List[WordSegment], text: str, language: str = "id"):
        self.words = words
        self.text = text
        self.language = language

def cleanup_vram() -> None:
    gc.collect()
    if torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        except Exception:
            pass

DEFAULT_INITIAL_PROMPT = (
    "Podcast, interview, conversation, commentary, storytelling, gaming, highlights, Mobile Legends."
)

def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    device: str = "cuda",
    compute_type: str = "float16",
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None
) -> Tuple[List[WordSegment], str]:
    from faster_whisper import WhisperModel

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    whisper_model = None
    all_words: List[WordSegment] = []
    text_segments: List[str] = []
    detected_lang: str = language or "id"

    try:
        print(f"[ClipMax Whisper] Menginisialisasi WhisperModel('{model_size}', device='{device}', compute_type='{compute_type}')...")
        whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
        prompt = initial_prompt if initial_prompt is not None else DEFAULT_INITIAL_PROMPT
        segments, info = whisper_model.transcribe(
            audio_path,
            word_timestamps=True,
            language=language,
            initial_prompt=prompt
        )
        if hasattr(info, "language") and info.language:
            detected_lang = info.language
            prob = getattr(info, "language_probability", 1.0)
            prob_val = float(prob) if isinstance(prob, (int, float)) else 1.0
            print(f"[ClipMax Whisper] Bahasa terdeteksi: {detected_lang} (probabilitas: {prob_val:.2f})")

        for segment in segments:
            t_text = segment.text.strip()
            if t_text:
                if hasattr(segment, "start") and hasattr(segment, "end") and isinstance(segment.start, (int, float)):
                    text_segments.append(f"[{segment.start:.2f}s - {segment.end:.2f}s] {t_text}")
                else:
                    text_segments.append(t_text)
            if segment.words:
                for w in segment.words:
                    clean_w = w.word.strip()
                    if clean_w:
                        all_words.append(
                            WordSegment(
                                word=clean_w,
                                start=round(float(w.start), 2),
                                end=round(float(w.end), 2),
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

    full_transcript = "\n".join(text_segments)
    return TranscriptionResult(all_words, full_transcript, detected_lang)
