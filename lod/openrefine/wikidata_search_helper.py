"""Stand-in for the search part of the Wikidata reconciliation service.

While wikidata-reconciliation.wmcloud.org is down, OpenRefine's "Search for
match" box (and the type/property boxes) get no answers. This small server
answers those searches from the Wikidata API instead, which keeps working.

Start it before working in OpenRefine, and leave the terminal open:
    python3 lod/openrefine/wikidata_search_helper.py
Stop it with Ctrl+C. It listens only on this computer (127.0.0.1:8000).

OpenRefine's Wikidata service settings point their "suggest" addresses here
(changed on 2026-10-22); the original settings are in
lod/openrefine/recon_settings_original.json.
"""
import json
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "OpenGadda data cleaning (OpenRefine search helper)"


def wikidata_search(text, kind):
    """Top Wikidata matches for text: items, or properties."""
    query = urllib.parse.urlencode({
        "action": "wbsearchentities", "format": "json", "search": text,
        "language": "it", "uselang": "it", "type": kind, "limit": 15,
    })
    # curl, not urllib: Python's own HTTPS certificates fail on this Mac
    out = subprocess.run(["curl", "-s", "--max-time", "15", "-A", USER_AGENT, f"{API}?{query}"],
                         capture_output=True, text=True).stdout
    try:
        found = json.loads(out).get("search", [])
    except ValueError:
        return []
    return [{"id": r["id"], "name": r.get("label", r["id"]), "description": r.get("description", "")}
            for r in found]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(url.query)
        text = (params.get("prefix") or params.get("query") or [""])[0].strip()
        kind = "property" if url.path.endswith("/property") else "item"
        body = json.dumps({"result": wikidata_search(text, kind) if text else []})
        callback = (params.get("callback") or [""])[0]
        if callback:  # older OpenRefine widgets ask for JSONP
            body = f"{callback}({body})"
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript" if callback else "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    print("Wikidata search helper running on http://127.0.0.1:8000 — leave this window open, Ctrl+C to stop.")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
