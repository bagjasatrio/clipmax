import pytest
from unittest.mock import patch, MagicMock
from clipmax.renderer import render_clip
from clipmax.reframe import SceneSegment

def test_render_clip_command_nvenc():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=True), \
         patch("os.path.exists", return_value=True):
        
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        out = render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=10.0,
            end_time=40.0,
            crop_x=650,
            ass_path=r"C:\temp\sub.ass",
            use_gpu=True,
            reframe_mode="CROP_TRACKING"
        )

        args = mock_popen.call_args[0][0]
        assert "-c:v" in args
        encoder_idx = args.index("-c:v") + 1
        assert args[encoder_idx] == "h264_nvenc"
        assert "subtitles='C\\:/temp/sub.ass'" in " ".join(args)

def test_render_clip_command_blurred_background():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=True), \
         patch("os.path.exists", return_value=True):
        
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        out = render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=5.0,
            end_time=35.0,
            crop_x=0,
            ass_path=r"C:\temp\sub.ass",
            use_gpu=True,
            reframe_mode="BLURRED_BACKGROUND"
        )

        args = mock_popen.call_args[0][0]
        assert "-filter_complex" in args
        fc_idx = args.index("-filter_complex") + 1
        fc_str = args[fc_idx]
        assert "boxblur=20:20" in fc_str
        assert "flags=lanczos" in fc_str
        assert "overlay=(W-w)/2:(H-h)/2" in fc_str
        assert "subtitles='C\\:/temp/sub.ass'" in fc_str
        assert "-c:v" in args

def test_render_clip_command_multi_scenes():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=True), \
         patch("os.path.exists", return_value=True):

        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        scenes = [
            SceneSegment(start_time=0.0, end_time=10.0, mode="CROP_TRACKING", crop_x="650"),
            SceneSegment(start_time=10.0, end_time=25.0, mode="BLURRED_BACKGROUND", crop_x="0"),
            SceneSegment(start_time=25.0, end_time=30.0, mode="CROP_TRACKING", crop_x="700"),
        ]

        render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=0.0,
            end_time=30.0,
            crop_x=650,
            ass_path=r"C:\temp\sub.ass",
            use_gpu=True,
            scenes=scenes
        )

        args = mock_popen.call_args[0][0]
        assert "-filter_complex" in args
        fc_idx = args.index("-filter_complex") + 1
        fc_str = args[fc_idx]
        assert "trim=start=0.000:end=10.000" in fc_str
        assert "trim=start=10.000:end=25.000" in fc_str
        assert "trim=start=25.000:end=30.000" in fc_str
        assert "concat=n=3:v=1:a=0" in fc_str
        assert "subtitles='C\\:/temp/sub.ass'" in fc_str
        assert "-c:v" in args

def test_render_clip_command_cpu_fallback():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=False), \
         patch("os.path.exists", return_value=True):
        
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=0.0,
            end_time=10.0,
            crop_x=0,
            ass_path="sub.ass",
            use_gpu=False
        )

        args = mock_popen.call_args[0][0]
        encoder_idx = args.index("-c:v") + 1
        assert args[encoder_idx] == "libx264"

def test_render_clip_single_scene_respects_scene_mode():
    with patch("subprocess.Popen") as mock_popen, \
         patch("clipmax.renderer.is_nvenc_supported", return_value=True), \
         patch("os.path.exists", return_value=True):

        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        # 1. Single scene with BLURRED_BACKGROUND (Screen share / presentation)
        scenes_blur = [SceneSegment(start_time=0.0, end_time=20.0, mode="BLURRED_BACKGROUND", crop_x="0")]
        render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=0.0,
            end_time=20.0,
            scenes=scenes_blur
        )
        args_blur = mock_popen.call_args[0][0]
        assert "-filter_complex" in args_blur
        fc_blur = args_blur[args_blur.index("-filter_complex") + 1]
        assert "boxblur=20:20" in fc_blur
        assert "flags=lanczos" in fc_blur
        assert "overlay=(W-w)/2:(H-h)/2" in fc_blur

        # 2. Single scene with CROP_9_16 (Centered talking head)
        scenes_crop = [SceneSegment(start_time=0.0, end_time=20.0, mode="CROP_9_16", crop_x="650")]
        render_clip(
            input_video="input.mp4",
            output_clip="output.mp4",
            start_time=0.0,
            end_time=20.0,
            scenes=scenes_crop
        )
        args_crop = mock_popen.call_args[0][0]
        assert "-vf" in args_crop
        vf_crop = args_crop[args_crop.index("-vf") + 1]
        assert "crop=ih*(9/16):ih:650:0" in vf_crop
        assert "scale=1080:1920" in vf_crop
