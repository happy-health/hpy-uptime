"""Mock /v2/status/internal endpoint for local preview."""

import json
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

MOCK_RESPONSE = {
    "services": [
        {"name": "API Gateway", "category": "Core Platform", "level": "operational", "description": "All 5 monitors OK", "monitor_count": 5, "alert_count": 0, "warn_count": 0},
        {"name": "API (Enso)", "category": "Core Platform", "level": "operational", "description": "All 3 monitors OK", "monitor_count": 3, "alert_count": 0, "warn_count": 0},
        {"name": "API (CRO)", "category": "Core Platform", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "Stytch Auth", "category": "Authentication", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},

        {"name": "Candid Health", "category": "Healthcare", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "Healthie", "category": "Healthcare", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "OpenLoop", "category": "Healthcare", "level": "operational", "description": "All 1 monitors OK", "monitor_count": 1, "alert_count": 0, "warn_count": 0},
        {"name": "Stripe", "category": "Payments", "level": "major", "description": "1/2 alerting: stripe-webhook-failures", "monitor_count": 2, "alert_count": 1, "warn_count": 0},
        {"name": "Shopify", "category": "Payments", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "DynamoDB", "category": "Database", "level": "operational", "description": "All 3 monitors OK", "monitor_count": 3, "alert_count": 0, "warn_count": 0},
        {"name": "Supabase", "category": "Database", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "Twilio", "category": "Communications", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
        {"name": "Customer.io", "category": "Communications", "level": "operational", "description": "All 1 monitors OK", "monitor_count": 1, "alert_count": 0, "warn_count": 0},
        {"name": "Slack", "category": "Communications", "level": "operational", "description": "All 1 monitors OK", "monitor_count": 1, "alert_count": 0, "warn_count": 0},
        {"name": "Datadog", "category": "Observability", "level": "operational", "description": "All 1 monitors OK", "monitor_count": 1, "alert_count": 0, "warn_count": 0},
        {"name": "Sentry", "category": "Observability", "level": "operational", "description": "All 1 monitors OK", "monitor_count": 1, "alert_count": 0, "warn_count": 0},
        {"name": "Inngest", "category": "Workflow", "level": "degraded", "description": "1/2 warning: inngest-function-failures", "monitor_count": 2, "alert_count": 0, "warn_count": 1},
        {"name": "AWS Lambda", "category": "Infrastructure", "level": "operational", "description": "All 4 monitors OK", "monitor_count": 4, "alert_count": 0, "warn_count": 0},
        {"name": "AWS S3", "category": "Infrastructure", "level": "operational", "description": "All 2 monitors OK", "monitor_count": 2, "alert_count": 0, "warn_count": 0},
    ],
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "total_monitors": 44,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/v2/status/internal" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            MOCK_RESPONSE["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.wfile.write(json.dumps(MOCK_RESPONSE).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs


print("Mock API running on http://localhost:9999")
HTTPServer(("", 9999), Handler).serve_forever()
