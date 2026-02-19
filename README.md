# hpy-uptime

**Live dashboard:** [https://happy-health.github.io/hpy-uptime/](https://happy-health.github.io/hpy-uptime/)

A stateless, single-page dependency status dashboard for Happy Health. Monitors 19 external services and auto-refreshes every 60 seconds.

## Overview

The dashboard fetches status directly from each provider's public API in the browser — no backend or database required. Services are grouped by category (Source Control, Cloud Infrastructure, Payments, etc.) with color-coded status indicators and summary counts.

### Working services (13/19 — no proxy needed)

| Service | API Type | Endpoint |
|---|---|---|
| GitHub | Statuspage | `/api/v2/status.json` |
| Bitbucket | Statuspage | `/api/v2/status.json` |
| npm Registry | Statuspage | `/api/v2/status.json` |
| PyPI | Statuspage | `/api/v2/status.json` |
| Shopify Payments | Statuspage | `/api/v2/status.json` |
| Datadog | Statuspage | `/api/v2/status.json` |
| Sentry | Statuspage | `/api/v2/status.json` |
| Customer.io | Statuspage | `/api/v2/status.json` |
| Twilio | Statuspage | `/api/v2/status.json` |
| GitLab | Status.io RSS | CORS-friendly RSS feed |
| Oracle Cloud | RSS | CORS-friendly RSS feed |
| Stytch | Instatus | `stytch.instatus.com/summary.json` |
| Eve | UptimeRobot | `status.eve.co/api/getMonitorList/...` |

### Services requiring a CORS proxy (6/19)

These services don't set `Access-Control-Allow-Origin` headers on their status APIs or feeds:

| Service | Feed/API URL | Why it's blocked |
|---|---|---|
| Stripe | `status.stripe.com/current` | JSON API, no CORS headers |
| PayPal | `paypal-status.com/feed/atom` | Atom feed, no CORS headers |
| AWS | `health.aws.amazon.com/health/status` | HTML only, RSS feed returns 404 |
| Microsoft Azure | `azurestatuscdn.azureedge.net/en-us/status/feed/` | XML feed, no CORS headers |
| Google Cloud | `status.cloud.google.com/feed.atom` | Atom feed, no CORS headers |
| Apple Developer | `apple.com/.../system_status_en_US.js` | JSONP endpoint, returns 403 with Origin |

To enable these, pass a CORS proxy URL as a query parameter:

```
https://happy-health.github.io/hpy-uptime/?proxy=https://your-worker.workers.dev
```

## Next steps

### Enable GitHub Pages

GitHub Pages is currently disabled at the org level. An org admin needs to:

1. Go to **https://github.com/organizations/happy-health/settings**
2. Navigate to **Member privileges**
3. Scroll to **Pages creation** and enable it
4. Then in **https://github.com/happy-health/hpy-uptime/settings/pages**, select **Deploy from a branch** > **`main`** / **`/ (root)`**

### Deploy a Cloudflare Worker CORS proxy

This unblocks the 6 remaining services. The free tier allows 100K requests/day.

1. Sign up at [workers.cloudflare.com](https://workers.cloudflare.com)
2. Create a new Worker with this code:

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = url.searchParams.get("url");
    if (!target) return new Response("Missing ?url= parameter", { status: 400 });

    const resp = await fetch(target, {
      headers: { "User-Agent": "hpy-uptime-proxy/1.0" },
    });

    const headers = new Headers(resp.headers);
    headers.set("Access-Control-Allow-Origin", "*");
    headers.set("Access-Control-Allow-Methods", "GET, OPTIONS");

    return new Response(resp.body, { status: resp.status, headers });
  },
};
```

3. Deploy and use the Worker URL: `?proxy=https://hpy-uptime-proxy.<your-account>.workers.dev`

### Alternative: GitHub Actions cron

Instead of a CORS proxy, a GitHub Actions workflow can fetch all statuses server-side every 5 minutes and commit a `status.json` file that the page reads. This avoids any CORS issues entirely but introduces a 5-minute data delay.

## Adding a new service

Edit the `SERVICES` array in `index.html`. Each entry needs a `name`, `category`, `statusUrl`, and `fetch` function.

### Atlassian Statuspage (most common)

Most SaaS providers use Atlassian Statuspage. Check for an API at `https://status.<domain>.com/api/v2/status.json`.

```javascript
{
  name: "New Service",
  category: "Category Name",
  statusUrl: "https://status.example.com",
  fetch: fetchStatuspage("https://status.example.com/api/v2/status.json"),
},
```

### Instatus

Look for `Powered by Instatus` in the footer. The API is at `https://<subdomain>.instatus.com/summary.json`.

```javascript
{
  name: "New Service",
  category: "Category Name",
  statusUrl: "https://status.example.com",
  fetch: fetchInstatus("https://example.instatus.com/summary.json"),
},
```

### UptimeRobot

Look for `Status page by UptimeRobot` in the footer. Find the page ID in the page source, then use `/api/getMonitorList/<pageId>`.

```javascript
{
  name: "New Service",
  category: "Category Name",
  statusUrl: "https://status.example.com",
  fetch: fetchUptimeRobot("https://status.example.com/api/getMonitorList/<pageId>"),
},
```

### RSS/Atom feed (CORS-friendly)

If the status page publishes an RSS or Atom feed with `Access-Control-Allow-Origin: *`, you can fetch it directly. Check with `curl -sI <feed-url> | grep access-control`.

```javascript
{
  name: "New Service",
  category: "Category Name",
  statusUrl: "https://status.example.com",
  fetch: fetchAtomFeed("https://status.example.com/feed.atom", false),
},
```

### RSS/Atom feed (needs CORS proxy)

Same as above but set the second parameter to `true` and add `needsProxy: true`:

```javascript
{
  name: "New Service",
  category: "Category Name",
  statusUrl: "https://status.example.com",
  fetch: fetchAtomFeed("https://status.example.com/feed.atom", true),
  needsProxy: true,
},
```

### Checking CORS support

```bash
curl -sI "https://status.example.com/api/v2/status.json" | grep -i access-control
```

If you see `access-control-allow-origin: *`, the service works directly. If not, you'll need the CORS proxy.
