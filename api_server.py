import aiohttp
from aiohttp import web
import asyncio
import pykka
import threading
from logs import register_logger

server_logger = register_logger("logs/api_server.log", "API Server")

routes = web.RouteTableDef()

@web.middleware
async def request_logger(request, handler):
    server_logger.debug(f"Got request: {request}")
    response = await handler(request)
    server_logger.debug(f"Sent response: {response}")
    return response

@routes.get('/')
async def handle(request):
    # redirect to the autoaquaponics.org website
    return aiohttp.web.HTTPFound('https://autoaquaponics.org')

def make_server_runner():
    app = web.Application()
    app.add_routes(routes)
    app.middlewares.append(request_logger)
    runner = web.AppRunner(app)
    return runner

class Server(pykka.ThreadingActor):
    def __init__(self, port=8080, server_logger=server_logger):
        super().__init__()
        self.logger = server_logger
        self.port = port
        self.event_loop = None
        self.thread = None

    def on_start(self):
        try:
            self.logger.info(f"Starting API server on port {self.port}")

            # build the web server object
            runner = make_server_runner()

            def worker():
                # run the application; copied from
                # https://stackoverflow.com/a/51610341
                self.event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.event_loop)
                self.event_loop.run_until_complete(runner.setup())
                site = web.TCPSite(runner, 'localhost', self.port)
                self.event_loop.run_until_complete(site.start())
                self.event_loop.run_forever()
            self.thread = threading.Thread(target=worker, daemon=True)
            self.thread.start()
        except Exception as e:
            self.logger.error(f"Error starting API server: {e}")
            raise e

    def on_stop(self):
        self.logger.info("Stopping API server")
        if self.event_loop:
            self.event_loop.stop()
        if self.thread:
            self.thread.join(timeout=1)

    def on_failure(self, failure):
        self.logger.error(f"API server actor failed: {failure}")
