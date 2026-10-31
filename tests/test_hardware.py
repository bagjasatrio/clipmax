import pytest
from unittest.mock import patch, MagicMock
from clipmax.hardware import (
    detect_hardware_specs,
    get_profile_tuning,
    tune_config_for_hardware,
    PROFILE_POTATO,
    PROFILE_MIDRANGE,
    PROFILE_HIGHEND,
    PROFILE_AUTO
)
from clipmax.config import AppConfig

def test_detect_hardware_specs():
    specs = detect_hardware_specs()
    assert "cpu_cores" in specs
    assert specs["cpu_cores"] >= 1
    assert "ram_gb" in specs
    assert specs["ram_gb"] > 0
    assert "available_encoders" in specs
    assert "detected_tier" in specs
    assert specs["detected_tier"] in (PROFILE_POTATO, PROFILE_MIDRANGE, PROFILE_HIGHEND)

def test_get_profile_tuning():
    specs = {
        "cpu_cores": 4,
        "ram_gb": 4.0,
        "cuda_available": False,
        "primary_encoder": "libx264",
        "has_nvenc": False,
    }
    potato_tune = get_profile_tuning(PROFILE_POTATO, specs)
    assert potato_tune["whisper_model"] == "tiny"
    assert potato_tune["primary_encoder"] == "libx264"
    assert potato_tune["encoder_preset"] == "ultrafast"
    assert potato_tune["reframe_sample_step"] == 45
    assert potato_tune["reframe_detect_width"] == 360

    mid_tune = get_profile_tuning(PROFILE_MIDRANGE, specs)
    assert mid_tune["whisper_model"] == "base"
    assert mid_tune["reframe_sample_step"] == 20

    high_tune = get_profile_tuning(PROFILE_HIGHEND, specs)
    assert high_tune["whisper_model"] in ("small", "base")
    assert high_tune["reframe_sample_step"] == 10

def test_tune_config_for_hardware():
    cfg = AppConfig()
    res = tune_config_for_hardware(cfg, PROFILE_POTATO)
    assert cfg.whisper_model == "tiny"
    assert cfg.reframe_sample_step == 45
    assert cfg.reframe_detect_width == 360
    assert res["applied_profile"] == PROFILE_POTATO

    res_high = tune_config_for_hardware(cfg, PROFILE_HIGHEND)
    assert cfg.reframe_sample_step == 10
    assert res_high["applied_profile"] == PROFILE_HIGHEND
