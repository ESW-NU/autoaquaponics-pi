import aiohttp
from aiohttp import web
import asyncio
import pykka
import threading
import cv2
import numpy as np
import time
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
async def handle_root(request):
    # redirect to the autoaquaponics.org website
    return aiohttp.web.HTTPFound('https://autoaquaponics.org')

def draw_pattern():
    img = np.full((480, 640, 3), 255, dtype=np.uint8)

    # Create an interesting pattern that changes over time
    t = time.time()

    # Make a copy of base image
    pattern_img = img.copy()

    # Draw animated sine wave pattern
    for x in range(0, 640, 5):
        y = int(240 + 100 * np.sin(x/50 + t))
        cv2.circle(pattern_img, (x, y), 3, (0, 127, 255), -1)

    # Draw animated circular pattern
    center_x = 320 + int(50 * np.cos(t))
    center_y = 240 + int(50 * np.sin(t))
    radius = int(100 + 20 * np.sin(2*t))
    cv2.circle(pattern_img, (center_x, center_y), radius, (255, 0, 127), 2)

    # Add some text
    cv2.putText(pattern_img, 'AutoAquaponics', (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    # Encode image to JPEG
    success, jpeg_img = cv2.imencode('.jpg', pattern_img)
    if not success:
        raise Exception("Failed to encode JPEG")
    return jpeg_img

# TODO move to stream.py
capture = None

@routes.get('/stream')
async def handle_websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    server_logger.debug("Websocket connection opened")

    try:
        while True:
            try:
                # check for any messages from client (including close) without blocking
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=0.001)
                    if msg.type == web.WSMsgType.CLOSE:
                        server_logger.debug("Client requested close")
                        break
                    elif msg.type == web.WSMsgType.ERROR:
                        server_logger.debug(f"WebSocket error: {ws.exception()}")
                        break
                except asyncio.TimeoutError:
                    # no message from client, continue with sending
                    pass

                # TODO this should be moved to stream.py
                # get the next frame
                global capture
                if capture is not None and capture.isOpened():
                    ret, frame = capture.read()
                    if ret:
                        success, jpeg_img = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        if not success:
                            jpeg_img = draw_pattern()
                    else:
                        jpeg_img = draw_pattern()
                else:
                    jpeg_img = draw_pattern()

                # send the frame
                await ws.send_bytes(jpeg_img.tobytes())

                # wait for the next frame
                await asyncio.sleep(0.033)
            except Exception as e:
                server_logger.error(f"Error streaming image: {str(e)}")
                break
    finally:
        if not ws.closed:
            await ws.close()
        server_logger.debug("Websocket connection closed")

    return ws


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

            # TODO move to stream.py
            # initialize capture object
            global capture
            capture = cv2.VideoCapture(0)
        except Exception as e:
            self.logger.error(f"Error starting API server: {e}")
            raise e

    def on_stop(self):
        self.logger.info("Stopping API server")
        if self.event_loop:
            self.event_loop.stop()
        if self.thread:
            self.thread.join(timeout=1)

        # TODO move to stream.py
        global capture
        if capture:
            capture.release()

    def on_failure(self, failure):
        self.logger.error(f"API server actor failed: {failure}")
