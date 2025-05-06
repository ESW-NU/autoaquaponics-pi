from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import shutil
import urllib.parse
from logs import register_logger
from pathlib import Path
import re
import os
import pykka
import threading

server_logger = register_logger("logs/server.log", "HTTP Server")

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
        server_logger.debug(format % args)

class Server(pykka.ThreadingActor):
    def __init__(self, port=8080, server_logger=server_logger):
        super().__init__()
        self.logger = server_logger
        self.port = port
        self.httpd = None
        self.thread = None

    def on_start(self):
        try:
            self.logger.info(f"Starting HTTP server on port {self.port}")
            self.httpd = HTTPServer(("", self.port), CustomRequestHandler)
            self.thread = threading.Thread(target=self.httpd.serve_forever).start()
        except Exception as e:
            self.logger.error(f"Error starting HTTP server: {e}")
            raise e

    def on_stop(self):
        self.logger.info("Stopping HTTP server")
        if self.httpd:
            self.httpd.shutdown()

    def on_failure(self, failure):
        self.logger.error(f"HTTP server actor failed: {failure}")
        self.on_stop()

    def on_receive(self, message):
        self.logger.warning(f"Received unknown message type: {type(message)}")
