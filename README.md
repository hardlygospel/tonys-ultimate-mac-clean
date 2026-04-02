# 🏠 Tony's Home Tunnel

**Route your internet traffic through your home connection — from work, from your phone, from anywhere.**

A self-contained macOS shell script that punches a secure, encrypted reverse proxy tunnel from your home Mac out to the internet, with zero router configuration, zero paid services, and zero dependencies beyond a free Cloudflare account.

---

## What It Does

When you're at work or on mobile data, your internet traffic exits through your employer's or carrier's network. That means different IP geolocation, potential content filtering, and no access to things tied to your home connection.

Tony's Home Tunnel solves this by turning your home Mac into a private proxy server and exposing it securely to the internet via [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/). Once running, any device you configure — work laptop, iPhone, Android — browses the web exactly as if it were sitting on your home desk.

```
[Your Device at Work]
        │
        │  HTTPS (encrypted)
        ▼
[Cloudflare Edge — mel01]
        │
        │  Secure tunnel (HTTP/2 over TCP)
        ▼
[Your Mac at Home — Tony's Home Tunnel]
        │
        │  Python HTTP/HTTPS proxy
        ▼
[The Open Internet — via your home ISP]
```

Your home Mac never needs an open port. Your router never needs touching. The tunnel originates as an *outbound* connection from your Mac to Cloudflare's servers, so your firewall and NAT stay exactly as they are.

---

## Benefits

### 🔐 Privacy from your workplace or carrier
All traffic from your configured device exits through your home IP, not your employer's corporate gateway or your mobile carrier. Websites see your home address, not your work one.

### 🌏 Your home geolocation, anywhere
Streaming services, banking apps, and regional websites that behave differently based on IP see your home location — useful when travelling or working remotely.

### 💸 Completely free
Uses Cloudflare's free Quick Tunnel service. No account required for basic use. No monthly fees. No bandwidth limits imposed by this tool.

### 🔒 Encrypted end-to-end
Traffic between your device and Cloudflare's edge is TLS-encrypted HTTPS. Traffic from Cloudflare to your Mac travels inside Cloudflare's own encrypted tunnel infrastructure. You're not sending traffic through any third-party proxy service.

### 🛠 No router changes required
Traditional reverse tunnels require port forwarding, dynamic DNS, and a static IP. This needs none of that. The tunnel is outbound-only — your router firewall is untouched.

### 📱 Works on any device
Configure it once on your iPhone, Android, work Mac, or Windows PC. Switch it on when you need it, off when you don't.

### 🏠 Works on home Wi-Fi too
When your phone is on the same Wi-Fi as your Mac, the script detects your Mac's LAN IP and gives you a direct connection address — no round-trip to Cloudflare needed.

### 🖥 Live activity monitor
See every connection in real time: who connected, what they requested, how much data flowed, and how long it took — all in a clean, colour-coded terminal feed.

### 😴 Sleep prevention built in
Uses macOS `caffeinate` to keep your Mac awake while the tunnel is running. The moment you press Ctrl+C, normal sleep behaviour returns.

### 🔁 Self-healing
A health monitor checks the proxy and Cloudflare tunnel every 20 seconds and automatically restarts either component if they crash. If the tunnel URL changes on restart, the new address is printed immediately.

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS | Any recent version (Intel or Apple Silicon) |
| Internet connection | On your home Mac |
| Homebrew | Auto-installed on first run if missing |
| cloudflared | Auto-installed via Homebrew on first run |
| Python 3 | Included with macOS / Homebrew — no packages needed |

---

## Quick Start

```bash
# 1. Make the script executable
chmod +x home_tunnel.sh HomeTunnel.command

# 2. Run it (or just double-click HomeTunnel.command in Finder)
bash home_tunnel.sh
```

On first run it will install Homebrew and `cloudflared` if needed (~2 minutes). After that, startup takes about 10 seconds.

---

## Connecting Your Devices

When the tunnel starts you'll see two sets of proxy settings printed clearly:

### Away from home (work network / mobile data)
```
Server : abc-xyz.trycloudflare.com
Port   : 443
```

**Work Mac:** System Settings → Network → \[your connection\] → Proxies → Secure Web Proxy (HTTPS)

**iPhone:** Settings → Wi-Fi → tap ⓘ on your network → Configure Proxy → Manual

**Android:** Settings → Wi-Fi → long-press network → Modify → Advanced → Proxy: Manual

**Windows:** Settings → Network & Internet → Proxy → Manual proxy setup

---

### On your home network (phone on same Wi-Fi as the Mac)
```
Server : 192.168.x.x   (your Mac's LAN IP, shown on startup)
Port   : 8888
```

Use the LAN IP and port directly — no need to go via Cloudflare.

> 💡 **Tip:** Set a DHCP reservation in your router (match by MAC address) to keep your Mac's local IP permanent, so your phone settings never need updating.

---

## Live Activity Feed

After the tunnel is live, every connection is logged in real time:

```
── Live Activity ────────────────────────────────────────────────────────
   time      client          destination                  status  size  ms
─────────────────────────────────────────────────────────────────────────
  ▶ 14:23:01  192.168.1.42   ⟶  apple.com:443
  ✓ 14:23:02  192.168.1.42   apple.com:443               ↑2KB ↓48KB 812ms
  ● 14:23:04  192.168.1.42   GET www.google.com          200  14KB  231ms
  ✓ 14:23:09  192.168.1.42   youtube.com:443             ↑8KB ↓2MB  4201ms
  ✗ 14:23:15  192.168.1.42   badsite.com:443             Connection refused
```

| Symbol | Meaning |
|---|---|
| `▶` | New HTTPS tunnel opened |
| `✓` | Tunnel closed — shows data transferred and duration |
| `●` | Plain HTTP request — green (2xx), yellow (3xx), red (4xx/5xx) |
| `✗` | Connection error |

---

## How It Works Under the Hood

1. **Python HTTP/HTTPS proxy** starts on port 8888 and binds to all network interfaces (`0.0.0.0`), making it reachable both from localhost (for Cloudflare) and from other devices on your LAN.

2. **Cloudflare Tunnel** (`cloudflared`) connects outbound from your Mac to Cloudflare's global edge network and exposes a public `*.trycloudflare.com` HTTPS URL that forwards to the local proxy. The `--protocol http2` flag forces TCP transport, which works even when your ISP or router blocks UDP/QUIC.

3. **Your device** is configured to use that URL as an HTTPS proxy. All browser traffic is sent there, encrypted, and Cloudflare forwards it down the tunnel to your Mac, which fetches it from the internet using your home connection.

4. **The health monitor** runs a loop every 20 seconds checking that the proxy, Cloudflare tunnel, and `caffeinate` processes are all alive — restarting any that have died.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Address already in use` on port 8888 | Script auto-kills the squatter. If it persists: `PROXY_PORT=9999 bash home_tunnel.sh` |
| QUIC timeout errors in log | Fixed — `--protocol http2` is set by default |
| No URL after 45 seconds | Check your internet connection and try again |
| Home Wi-Fi proxy says no internet | Use the LAN IP + port 8888, not the Cloudflare URL |
| macOS firewall blocking LAN devices | System Settings → Network → Firewall → Options → allow python3 |
| Tunnel drops after Mac sleeps | `caffeinate` prevents this, but check Energy Saver settings too |
| URL changed after restart | Normal — the new URL is printed automatically |
| Work network blocks `trycloudflare.com` | Sign up for a free Cloudflare account and use a named tunnel with your own domain |

**Full log file:** `~/Library/Logs/HomeTunnel/tunnel.log`

---

## Getting a Permanent URL (Optional)

The free Quick Tunnel generates a new random URL every restart. If you want a permanent address:

1. Sign up free at [dash.cloudflare.com](https://dash.cloudflare.com)
2. Add a domain (or use Cloudflare's free subdomain service)
3. Run `cloudflared tunnel login`
4. Run `cloudflared tunnel create home-proxy`
5. In `home_tunnel.sh`, replace the `cloudflared tunnel` line with:
   ```bash
   cloudflared tunnel run --url http://127.0.0.1:$PROXY_PORT home-proxy
   ```

---

## Security Considerations

- The Cloudflare URL is publicly accessible to anyone who knows it. The random subdomain provides obscurity by default, but you should not share it.
- Traffic between your device and Cloudflare is TLS 1.3 encrypted.
- Traffic between Cloudflare and your Mac is inside Cloudflare's own tunnel — it never traverses the open internet unencrypted.
- For additional security, Cloudflare Access (free tier) can be placed in front of the tunnel to require authentication before anyone can use it.
- No credentials, tokens, or personal data are stored by this script.

---

## Files

```
HomeTunnel/
├── home_tunnel.sh       # The tunnel script — everything lives here
├── HomeTunnel.command   # Double-click launcher for macOS Finder
└── README.md            # This file
```

---

## Author

**Tony** — 2026

Built for personal use. Free to use, modify, and share.

---

*Powered by [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (free tier) and Python's standard library. No third-party Python packages required.*
