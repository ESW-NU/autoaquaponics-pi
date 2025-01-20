from http.server import SimpleHTTPRequestHandler, HTTPServer
from main import Task
from logs import global_logger

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS header before finishing headers
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

class Server(Task):
    def __init__(self, port=8080):
        self.port = port
        self.httpd = HTTPServer(("", port), CORSRequestHandler)

    def start(self):
        global_logger.info(f"Serving on port {self.port} with CORS enabled")
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()
