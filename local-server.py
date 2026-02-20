"""
Local dev server for hpy-uptime.
Replaces both `python3 -m http.server 8787` and `mock-api.py`.

Usage:
    python3 local-server.py                              # mock mode (no DD keys needed)
    DD_API_KEY=xxx DD_APP_KEY=yyy python3 local-server.py  # live Datadog data

Routes:
    GET /proxy?url=<encoded_url>   — CORS proxy for external status pages
    GET /v2/status/internal        — Datadog monitor data (live or mock)
    GET /*                         — Static file server
"""

import json
import os
import random
import ssl
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", 8787))
DD_API_KEY = os.environ.get("DD_API_KEY", "")
DD_APP_KEY = os.environ.get("DD_APP_KEY", "")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "test")
MOCK_MODE = not (DD_API_KEY and DD_APP_KEY)

# ── Service definitions ───────────────────────────────────────────────────
# Tags can be "service:xxx", "integration:xxx", or "monitor_pack:xxx".
# A monitor matches a service if ANY of its tags appear in the service's tag list.

SERVICE_DEFINITIONS = [
    ("API Gateway",   "Core Platform",    ["service:hpy-api"]),
    ("API (Enso)",    "Core Platform",    ["service:hpy-api-enso"]),
    ("API (CRO)",     "Core Platform",    ["service:hpy-api-cro"]),
    ("Stytch Auth",   "Authentication",   ["service:stytch"]),
    ("Candid Health", "Healthcare",       ["service:candid"]),
    ("Healthie",      "Healthcare",       ["service:healthie"]),
    ("OpenLoop",      "Healthcare",       ["service:openloop"]),
    ("Stripe",        "Payments",         ["service:stripe"]),
    ("Shopify",       "Payments",         ["service:shopify"]),
    ("DynamoDB",      "Database",         ["service:dynamodb"]),
    ("Supabase",      "Database",         ["service:supabase"]),
    ("Twilio SMS (US)", "Communications", ["service:twilio"]),
    ("Customer.io",   "Communications",   ["service:customerio"]),
    ("Slack",         "Communications",   ["service:slack"]),
    ("Datadog",       "Observability",    ["service:datadog"]),
    ("Sentry",        "Observability",    ["service:sentry"]),
    ("Inngest",       "Workflow",         ["service:inngest"]),
    ("AWS Lambda",    "Infrastructure",   ["service:aws-lambda"]),
    ("AWS S3",        "Infrastructure",   ["service:aws-s3"]),
    # Infrastructure monitors matched by integration/pack tags
    ("AWS RDS",       "Database",         ["integration:amazon_rds", "monitor_pack:rds"]),
    ("Host Health",   "Infrastructure",   ["integration:host", "monitor_pack:host"]),
    ("Disk Health",   "Infrastructure",   ["integration:disk"]),
]

# Build a lookup: tag value -> list of (service_name, category)
TAG_TO_SERVICES = {}
for name, category, tags in SERVICE_DEFINITIONS:
    for tag in tags:
        TAG_TO_SERVICES.setdefault(tag, []).append((name, category))

# ── Team → Service mappings ──────────────────────────────────────────────
# Which teams/audiences are affected by each service.
# Services can appear in multiple teams.

TEAM_MAPPINGS = {
    "End Users": [
        "API Gateway", "API (Enso)", "API (CRO)",
        "Stytch Auth",
        "Stripe", "Shopify",
        "DynamoDB", "Supabase",
        "Twilio SMS (US)",
        "AWS Lambda", "AWS S3",
        "Cloudflare", "Vercel",
        "AWS RDS", "Host Health",
    ],
    "Clinicians": [
        "API Gateway",
        "Stytch Auth",
        "Candid Health", "Healthie", "OpenLoop",
        "DynamoDB", "Supabase",
        "Twilio SMS (US)",
        "AWS RDS", "Host Health",
    ],
    "Developers": [
        "Datadog", "Sentry",
        "Inngest",
        "AWS Lambda", "AWS S3",
        "AWS RDS", "Host Health", "Disk Health",
        "GitHub", "Bitbucket", "GitLab",
        "npm Registry", "PyPI",
        "Cloudflare", "Vercel",
    ],
    "Customer Support": [
        "Slack", "Customer.io", "Twilio SMS (US)",
        "Datadog", "Sentry",
        "Stytch Auth",
        "Stripe", "Shopify",
    ],
}

# Build reverse lookup: service name -> list of audiences
SERVICE_AUDIENCES = {}
for team, services in TEAM_MAPPINGS.items():
    for svc_name in services:
        SERVICE_AUDIENCES.setdefault(svc_name, []).append(team)


# ── Mock data generation ─────────────────────────────────────────────────

# Realistic monitor counts per service
MOCK_MONITOR_COUNTS = {
    "API Gateway": 5, "API (Enso)": 3, "API (CRO)": 2,
    "Stytch Auth": 2, "Candid Health": 2,
    "Healthie": 2, "OpenLoop": 1, "Stripe": 2, "Shopify": 2,
    "DynamoDB": 3, "Supabase": 2, "Twilio SMS (US)": 2, "Customer.io": 1,
    "Slack": 1, "Datadog": 1, "Sentry": 1, "Inngest": 2,
    "AWS Lambda": 4, "AWS S3": 2,
    "AWS RDS": 3, "Host Health": 7, "Disk Health": 2,
}

# Services that will randomly show issues (makes the dashboard look realistic)
MOCK_FLAKY_SERVICES = [

    ("Stripe", "alert", "stripe-webhook-failures"),
    ("Inngest", "warn", "inngest-function-failures"),
    ("API (CRO)", "warn", "cro-api-p99-latency"),
    ("OpenLoop", "alert", "openloop-availability"),
]


def generate_mock_data():
    """Generate realistic mock internal service data."""
    # Pick 1-3 random services to show issues
    num_issues = random.randint(1, 3)
    flaky = random.sample(MOCK_FLAKY_SERVICES, min(num_issues, len(MOCK_FLAKY_SERVICES)))
    flaky_map = {name: (severity, monitor) for name, severity, monitor in flaky}

    services = []
    total = 0
    for name, category, tags in SERVICE_DEFINITIONS:
        count = MOCK_MONITOR_COUNTS.get(name, 2)
        total += count

        if name in flaky_map:
            severity, monitor_name = flaky_map[name]
            if severity == "alert":
                services.append({
                    "name": name, "category": category, "level": "major",
                    "description": f"1/{count} alerting: {monitor_name}",
                    "monitor_count": count, "alert_count": 1, "warn_count": 0,
                })
            else:
                services.append({
                    "name": name, "category": category, "level": "degraded",
                    "description": f"1/{count} warning: {monitor_name}",
                    "monitor_count": count, "alert_count": 0, "warn_count": 1,
                })
        else:
            services.append({
                "name": name, "category": category, "level": "operational",
                "description": f"All {count} monitors OK",
                "monitor_count": count, "alert_count": 0, "warn_count": 0,
            })

    # Build tags lookup for enrichment
    tags_by_name = {name: tags for name, _, tags in SERVICE_DEFINITIONS}
    for svc in services:
        svc["audiences"] = SERVICE_AUDIENCES.get(svc["name"], [])
        svc["tags"] = tags_by_name.get(svc["name"], [])

    return {
        "services": services,
        "total_monitors": total,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "mock": True,
    }


# ── Live Datadog fetching ────────────────────────────────────────────────

def fetch_datadog_monitors():
    """Fetch all monitors from Datadog API and aggregate by service tag."""
    url = "https://api.datadoghq.com/api/v1/monitor"
    req = urllib.request.Request(url, headers={
        "DD-API-KEY": DD_API_KEY,
        "DD-APPLICATION-KEY": DD_APP_KEY,
        "Content-Type": "application/json",
    })

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            monitors = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return None, f"Datadog API error: HTTP {e.code}"
    except Exception as e:
        return None, f"Datadog API error: {e}"

    # Aggregate monitors per service
    service_stats = {}
    for name, category, tags in SERVICE_DEFINITIONS:
        service_stats[name] = {
            "category": category, "tags": tags,
            "alert": 0, "warn": 0, "ok": 0, "total": 0,
            "alert_names": [], "warn_names": [],
        }

    total_matched = 0
    for monitor in monitors:
        monitor_tags = monitor.get("tags", [])
        state = monitor.get("overall_state", "OK")
        monitor_name = monitor.get("name", "unnamed")
        monitor_id = monitor.get("id", monitor_name)

        # Find all services this monitor matches (dedup per service)
        matched_services = set()
        for tag in monitor_tags:
            if tag in TAG_TO_SERVICES:
                for svc_name, _ in TAG_TO_SERVICES[tag]:
                    matched_services.add(svc_name)

        for svc_name in matched_services:
            stats = service_stats[svc_name]
            stats["total"] += 1
            total_matched += 1
            if state == "Alert":
                stats["alert"] += 1
                stats["alert_names"].append(monitor_name)
            elif state == "Warn":
                stats["warn"] += 1
                stats["warn_names"].append(monitor_name)
            else:
                stats["ok"] += 1

    services = []
    for name, category, tags in SERVICE_DEFINITIONS:
        stats = service_stats[name]
        if stats["alert"] > 0:
            level = "major"
            desc = f"{stats['alert']}/{stats['total']} alerting: {', '.join(stats['alert_names'][:3])}"
        elif stats["warn"] > 0:
            level = "degraded"
            desc = f"{stats['warn']}/{stats['total']} warning: {', '.join(stats['warn_names'][:3])}"
        elif stats["total"] > 0:
            level = "operational"
            desc = f"All {stats['total']} monitors OK"
        else:
            level = "unknown"
            desc = "Not monitored in Datadog"

        services.append({
            "name": name, "category": category, "level": level,
            "description": desc, "monitor_count": stats["total"],
            "alert_count": stats["alert"], "warn_count": stats["warn"],
        })

    tags_by_name = {name: tags for name, _, tags in SERVICE_DEFINITIONS}
    for svc in services:
        svc["audiences"] = SERVICE_AUDIENCES.get(svc["name"], [])
        svc["tags"] = tags_by_name.get(svc["name"], [])

    return {
        "services": services,
        "total_monitors": total_matched,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "mock": False,
    }, None


# ── HTTP Handler ─────────────────────────────────────────────────────────

class LocalHandler(SimpleHTTPRequestHandler):
    """Handles /proxy, /v2/status/internal, and static files."""

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/proxy":
            self._handle_proxy(parsed)
        elif parsed.path == "/v2/status/internal":
            self._handle_internal()
        else:
            super().do_GET()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def _json_response(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _handle_proxy(self, parsed):
        """CORS proxy: fetch the target URL server-side and relay the response."""
        params = parse_qs(parsed.query)
        target_url = params.get("url", [None])[0]

        if not target_url:
            self._json_response(400, {"error": "Missing ?url= parameter"})
            return

        try:
            req = urllib.request.Request(target_url, headers={
                "User-Agent": "hpy-uptime-proxy/1.0",
                "Accept": "*/*",
            })
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "application/octet-stream")
                body = resp.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self._json_response(e.code, {"error": f"Upstream HTTP {e.code}"})
        except Exception as e:
            self._json_response(502, {"error": f"Proxy error: {e}"})

    def _handle_internal(self):
        """Return Datadog monitor data (live) or mock data (no DD keys)."""
        api_key = self.headers.get("API_KEY", "")
        if LOCAL_API_KEY and api_key != LOCAL_API_KEY:
            self._json_response(401, {"error": "Invalid API_KEY header"})
            return

        if MOCK_MODE:
            self._json_response(200, generate_mock_data())
            return

        data, error = fetch_datadog_monitors()
        if error:
            # Fall back to mock data on Datadog errors, with error noted
            mock = generate_mock_data()
            mock["datadog_error"] = error
            self._json_response(200, mock)
            return

        self._json_response(200, data)

    def log_message(self, format, *args):
        status = args[1] if len(args) > 1 else ""
        method_path = args[0] if args else ""
        print(f"  {method_path} -> {status}")


def main():
    server = HTTPServer(("", PORT), LocalHandler)

    mode = "MOCK" if MOCK_MODE else "LIVE"
    print()
    print(f"  hpy-uptime local server ({mode} mode)")
    print(f"  {'=' * 40}")
    print()
    print(f"  Public:    http://localhost:{PORT}/")
    print(f"  Internal:  http://localhost:{PORT}/internal.html")
    print(f"  Proxy:     http://localhost:{PORT}/proxy?url=...")
    print()
    if MOCK_MODE:
        print(f"  Datadog:   MOCK (set DD_API_KEY + DD_APP_KEY for live data)")
    else:
        print(f"  Datadog:   LIVE (keys configured)")
    print(f"  API Key:   {LOCAL_API_KEY!r}")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
