import subprocess
from logs import global_logger, setup_logger
from main import Task

"""
This module handles starting an ffmpeg process to encode video from a camera
device into a stream. The stream is output as HLS segments and a manifest file
for use in a web player.
"""

stream_logger = setup_logger("logs/stream.log", "Stream Encoder")

class Stream(Task):
    def __init__(self, stream_data_output_dir="stream_output", device_path="/dev/video0", stream_logger=stream_logger):
        self.stream_logger = stream_logger
        self.ffmpeg_command = [
            "ffmpeg",
            "-f", "v4l2",
            "-input_format", "yuv422p",
            "-video_size", "1280x720",
            "-framerate", "10",
            "-i", device_path,
            "-c:v", "libx264",
            "-profile:v", "baseline",
            "-level:v", "3.1",
            "-pix_fmt", "yuv420p",
            "-b:v", "1000k",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-g", "48",
            "-c:a", "aac",
            "-f", "hls",
            "-hls_time", "5",
            "-hls_list_size", "10",
            "-hls_flags", "delete_segments",
            "-hls_segment_filename", f"{stream_data_output_dir}/stream%d.ts",
            f"{stream_data_output_dir}/stream.m3u8"
        ]
        self.ffmpeg_process = None

    def start(self):
        global_logger.info(f"starting stream encoding with command: {' '.join(self.ffmpeg_command)}")
        self.ffmpeg_process = subprocess.Popen(self.ffmpeg_command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for line in self.ffmpeg_process.stderr:
            self.stream_logger.info(line.decode("utf-8").strip())

    def stop(self):
        global_logger.info("stopping stream encoding")
        self.ffmpeg_process.terminate()
        try:
            self.ffmpeg_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.ffmpeg_process.kill()
            global_logger.warning("ffmpeg process killed due to timeout")
