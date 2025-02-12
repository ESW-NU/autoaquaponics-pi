from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import shutil
import urllib.parse
from main import Task
from logs import global_logger, setup_logger
from pathlib import Path
import re
import os

server_logger = setup_logger("logs/server.log", "HTTP Server")

def translate_path(relative_path: str) -> Path | None:
    cwd = Path.cwd()

    # convert the path to absolute, resolving all ".." and symlinks
    full_path = (cwd / Path(relative_path)).resolve()

    # ensure the path is still within base_dir
    if not full_path.is_relative_to(cwd):
        return None

    return full_path

class CustomRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # parse the url
        url_parts = urllib.parse.urlparse(self.path)

        # match on all the routes we want to support

        if match := re.match(r"^/stream/([^/]+.ts)$", url_parts.path):
            file_path = translate_path(f"stream_output/{match.group(1)}")
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            return self.handle_get_file(file_path, mime_type="video/MP2T")
        elif match := re.match(r"^/stream/([^/]+.m3u8)$", url_parts.path):
            file_path = translate_path(f"stream_output/{match.group(1)}")
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return
            return self.handle_get_file(file_path, mime_type="application/x-mpegURL")

        self.send_error(404, "Not found")

    def handle_get_file(self, file_path: Path, mime_type: str = None) -> None:
        server_logger.info(f"serving from {file_path}")

        # caller ensures file path is safe and totally not a security risk

        # find the corresponding file in the filesystem
        try:
            file = open(file_path, 'rb')
            file_stats = os.fstat(file.fileno())
        except OSError:
            server_logger.error(f"error opening file {file_path}")
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        # send the response
        try:
            # TODO use browser cache if possible; see library implementation of
            # SimpleHTTPRequestHandler

            self.send_response(HTTPStatus.OK)
            if mime_type is not None:
                self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_stats.st_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            shutil.copyfileobj(file, self.wfile)
        except:
            file.close()
            raise

    def log_message(self, format, *args):
        server_logger.info(format % args)

class Server(Task):
    def __init__(self, port=8080):
        self.port = port
        self.httpd = HTTPServer(("", port), CustomRequestHandler)

    def start(self):
        global_logger.info(f"Serving on port {self.port} with CORS enabled")
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()
