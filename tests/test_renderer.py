import pytest
from unittest.mock import patch, MagicMock
from clipmax.renderer import render_clip

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
        assert "boxblur=25:5" in fc_str
        assert "overlay=(W-w)/2:(H-h)/2" in fc_str
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
