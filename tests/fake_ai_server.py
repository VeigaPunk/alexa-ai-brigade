# -*- coding: utf-8 -*-
"""Local stand-in for both the OpenAI-compatible LLM endpoint and the
Alexa directives endpoint. Records every request it receives."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeAIHandler(BaseHTTPRequestHandler):
    server_version = "FakeAI/1.0"

    def log_message(self, *args):
        pass  # keep test output clean

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append({"path": self.path, "body": body,
                                     "headers": dict(self.headers)})

        if self.path == "/chat/completions":
            if self.server.error_status:
                self._reply(self.server.error_status,
                            {"error": {"message": "test provider error",
                                       "type": "test"}})
                return
            if self.server.sleep_seconds:
                time.sleep(self.server.sleep_seconds)
            if self.server.trickle_seconds:
                # headers arrive promptly, body dribbles in slowly
                reply = {
                    "choices": [{"message": {
                        "role": "assistant",
                        "content": self.server.next_answer},
                        "finish_reason": "stop"}]
                }
                data = json.dumps(reply).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                chunk = max(1, len(data) // 10)
                for i in range(0, len(data), chunk):
                    self.wfile.write(data[i:i + chunk])
                    self.wfile.flush()
                    time.sleep(self.server.trickle_seconds / 10.0)
                return
            reply = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": self.server.next_answer,
                        },
                        "finish_reason": "stop",
                    }
                ]
            }
            self._reply(200, reply)
        elif self.path == "/v1/directives":
            if self.server.directives_sleep:
                time.sleep(self.server.directives_sleep)
            self._reply(204, {})
        else:
            self._reply(404, {"error": "unknown path"})

    def _reply(self, code, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeAIServer:
    def __init__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAIHandler)
        self.server.requests = []
        self.server.next_answer = "Resposta de teste do assistente."
        self.server.sleep_seconds = 0.0
        self.server.directives_sleep = 0.0
        self.server.trickle_seconds = 0.0
        self.server.error_status = 0
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        host, port = self.server.server_address
        return "http://%s:%d" % (host, port)

    def requests_for(self, path):
        return [r for r in self.server.requests if r["path"] == path]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
