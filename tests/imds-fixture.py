#!/usr/bin/env python3

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_PUT(self):
        if self.path != "/latest/api/token":
            self.send_error(404)
            return
        self.reply("synthetic-token")

    def do_GET(self):
        if self.path == "/":
            self.reply("ok")
        elif self.path == "/latest/meta-data/iam/security-credentials/":
            self.reply("synthetic-role")
        elif self.path == "/latest/meta-data/iam/security-credentials/synthetic-role":
            print("credential-request", flush=True)
            self.reply(
                json.dumps(
                    {
                        "Code": "Success",
                        "LastUpdated": "2026-07-29T00:00:00Z",
                        "Type": "AWS-HMAC",
                        "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
                        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                        "Token": "synthetic-session-token",
                        "Expiration": "2036-07-29T00:00:00Z",
                    }
                )
            )
        else:
            self.send_error(404)

    def log_message(self, _format, *_args):
        pass

    def reply(self, body):
        payload = body.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


ThreadingHTTPServer(("0.0.0.0", 18080), Handler).serve_forever()
