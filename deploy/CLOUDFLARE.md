# riverglyph.enablesu.com: the live app via Cloudflare Tunnel

Publishes the **live app you run locally**: `python serve.py`, which serves the
order flow and real renders from `cache/`. Visitors to the bare domain get the
customer landing page (`start.html`); Studio is at `/studio.html`. It's available at
**https://riverglyph.enablesu.com**, behind HTTP Basic Auth. The user and the
password are the **same** long random passphrase. No NAS is needed.

```
browser ──HTTPS──▶ Cloudflare edge ──tunnel──▶ cloudflared (the hosting Mac)
   ──▶ 127.0.0.1:8081  deploy/auth_proxy.py   (Basic Auth check; "/" → start.html)
   ──▶ 127.0.0.1:8765  python serve.py         (the app you already run)
```

- **TLS** is handled by Cloudflare. No ports are opened on the router or
  firewall; cloudflared makes outbound connections only.
- **Auth** is enforced by `deploy/auth_proxy.py` (stdlib only). It refuses to
  start without credentials and compares them in constant time. It sends
  `Cache-Control: private, no-store` so Cloudflare never caches protected pages.
  It returns a clear 502 when `serve.py` isn't running.
- Both the proxy and `serve.py` listen on **127.0.0.1 only**, so the tunnel is
  the only way in from outside.
- Anyone with the passphrase gets the **whole app**: they can list and edit
  orders (which include customer names and addresses) and start renders on this
  Mac. Share it only with people you trust with that.

## What runs where

| Piece | How it runs | Log |
|-------|-------------|-----|
| `serve.py` (the app) | **you start it**: `python serve.py` (as you do today) | its terminal |
| Auth proxy | LaunchAgent `com.enablesu.riverglyph-proxy`, starts at login | `~/Library/Logs/riverglyph-proxy.log` |
| Tunnel | LaunchAgent `com.enablesu.riverglyph-tunnel`, starts at login | `~/Library/Logs/riverglyph-tunnel.log` |

**The site is up only while `serve.py` is running and the Mac is awake.** If
`serve.py` is stopped, logged-in visitors see *"riverglyph app is not running"*.
If the Mac is asleep, everyone sees Cloudflare error 1033.

## Don't disturb the bridge-james tunnel

Both Macs have a `~/.cloudflared/config.yml` for the **`bridge-james`** tunnel
(`mobile-prep` / `mobile-vista.enablesu.com`), which runs on the **desktop Mac**.

> **Don't** run `cloudflared tunnel run` with no arguments, and **don't** run
> `cloudflared service install`. Both read `config.yml`. On the laptop that would
> add a second `bridge-james` connector and steal mobile-prep traffic. On the
> desktop it would replace the existing service.

riverglyph has **its own tunnel**, its own config file
(`~/.cloudflared/riverglyph.yml`) and its own LaunchAgents, so it runs **next
to** bridge-james on the desktop without interfering. Leave `config.yml`
unchanged on both machines.

**Fixed values:** tunnel `riverglyph` = `4c3ed387-005c-47e2-8d3a-7d25bbd0a131`.
The CNAME `riverglyph.enablesu.com` points at that tunnel, not at a machine, so
the DNS record **never changes** when you move Macs.

## Install on a Mac (or move to another one)

**Only one Mac may run the riverglyph tunnel at a time.** If two run it,
Cloudflare splits visitors between them, and each Mac has its own orders.

### On the new Mac: prepare (the site stays on the old Mac)

1. **Get the code.** The deploy files must be committed and pushed (or copied):
   `git clone …` / `git pull`.
2. **Python env** (Python 3.12+), as in `CLAUDE.md`:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .
   ```
3. **cloudflared:** `brew install cloudflared` (the desktop already has it).
4. **Copy the files git doesn't carry** (the landing images *are* in git) from the old Mac (AirDrop, `scp`, or a USB
   drive; the first two are secrets, so don't email them or put them in a
   shared drive):

   | From the old Mac | To the same place on the new Mac | Why |
   |------------------|-----------------------------------|-----|
   | `~/.cloudflared/4c3ed387-005c-47e2-8d3a-7d25bbd0a131.json` | `~/.cloudflared/` | tunnel secret (the tunnel's identity) |
   | `deploy/riverglyph.env` | `deploy/` | the login passphrase (`chmod 600` it) |
   | `output/orders/` | `output/orders/` | existing orders, if you want to keep them |
   | `cache/` | `cache/` | hydrography data `serve.py` renders from (large) |

   **No copying needed for the tunnel secret** if the new Mac is logged in to
   Cloudflare (`~/.cloudflared/cert.pem` exists). Download it there instead. Pass
   the **UUID**, not the name, so `config.yml`'s `bridge-james` can't be picked up:
   ```bash
   cloudflared tunnel token --cred-file ~/.cloudflared/4c3ed387-005c-47e2-8d3a-7d25bbd0a131.json \
     4c3ed387-005c-47e2-8d3a-7d25bbd0a131
   ```
   For the passphrase, you can instead run `bash deploy/gen-riverglyph-credentials.sh`
   (this creates a **new** passphrase).

   Example with `scp` (from the new Mac, laptop reachable as `laptop.local`):
   ```bash
   scp laptop.local:.cloudflared/4c3ed387-005c-47e2-8d3a-7d25bbd0a131.json ~/.cloudflared/
   scp laptop.local:code/gms/hydro-art/deploy/riverglyph.env deploy/ && chmod 600 deploy/riverglyph.env
   rsync -a laptop.local:code/gms/hydro-art/output/orders/ output/orders/
   rsync -a laptop.local:code/gms/hydro-art/cache/ cache/
   ```
5. **Start the app and check it locally:** `python serve.py`, then open
   http://127.0.0.1:8765/start.html.

### Switch over (about a minute of downtime)

```bash
# on the OLD Mac
bash deploy/install-riverglyph.sh uninstall    # stops proxy + tunnel, removes the LaunchAgents

# on the NEW Mac (repo root)
bash deploy/install-riverglyph.sh              # writes ~/.cloudflared/riverglyph.yml, installs + starts both
bash deploy/install-riverglyph.sh status
cloudflared tunnel info riverglyph             # exactly ONE connector, the new Mac's
```

The install script fills in this Mac's repo path, home folder and `cloudflared`
location. It checks that the tunnel secret, `riverglyph.env` and `.venv` are
present before it starts anything. It never touches `config.yml`. Re-running it
is safe; it reinstalls.

Then open https://riverglyph.enablesu.com in a private window and log in.

On a desktop, also turn on *System Settings → Energy → Prevent automatic
sleeping when the display is off*, and start `serve.py` after each reboot.

## Creating the tunnel from scratch (reference; already done 2026-10-04)

Only needed if the tunnel is deleted. Requires `~/.cloudflared/cert.pem` (from
`cloudflared tunnel login`, choosing the `enablesu.com` zone).

```bash
cloudflared tunnel create riverglyph           # prints the new <TUNNEL-UUID>, writes its .json
export RIVERGLYPH_TUNNEL_ID=<TUNNEL-UUID>       # and update TUNNEL_ID in install-riverglyph.sh
bash deploy/install-riverglyph.sh              # writes ~/.cloudflared/riverglyph.yml
cloudflared tunnel --config ~/.cloudflared/riverglyph.yml route dns --overwrite-dns \
  "$RIVERGLYPH_TUNNEL_ID" riverglyph.enablesu.com
# → "Added CNAME riverglyph.enablesu.com ... tunnelID=<TUNNEL-UUID>"
```

> **Gotcha (hit during setup):** a plain `cloudflared tunnel route dns riverglyph …`
> picks up `tunnel: bridge-james` from the default `config.yml`. It then points
> the CNAME at the **wrong tunnel** (log shows `tunnelID=9cae03c1…`). Always pass
> `--config ~/.cloudflared/riverglyph.yml`, and check that the `tunnelID` in the
> output is the riverglyph UUID.

**Credentials:** `deploy/riverglyph.env` (git-ignored, mode 600). The user and
the password are the same phrase: 8 random dictionary words plus a number
(~130 bits). To rotate it:
`rm deploy/riverglyph.env && bash deploy/gen-riverglyph-credentials.sh`, then
restart the proxy (see *Day-to-day*).

## Landing-page images

`start.html` loads its images from `/output/…`. `serve.py` only serves `web/`,
so the proxy serves `/output/*` itself from `deploy/output/` (read-only, behind
the login). The four `deploy/output/landing/*.webp` files are **committed**, so a
fresh clone has them. The NAS originals weren't available, so this set
(2026-10-04) was built from other committed files:

| Page image | Built from |
|------------|------------|
| `landing/clark-poster.webp` | `market-analysis/thumbs/clark_county.jpg` |
| `landing/wa-elevation.webp` | `market-analysis/thumbs/washington_elevation_peak.jpg` |
| `landing/clark-flow.webp` | `market-analysis/thumbs/monthly_flow_clark_county_24f.jpg`: a **still frame**, not the animated GIF |
| `landing/clark-report.webp` | `python3 tools/build_report_card.py` from `notebooks/figures/` (committed) |
| `gallery/conus-neon-hero/conus-neon-hero.png` | **missing**: never rendered (`tools/render_conus.py`, needs all-states data) |

```bash
T=market-analysis/thumbs L=deploy/output/landing; mkdir -p $L
cwebp -q 82 $T/clark_county.jpg -o $L/clark-poster.webp
cwebp -q 82 $T/washington_elevation_peak.jpg -o $L/wa-elevation.webp
cwebp -q 82 $T/monthly_flow_clark_county_24f.jpg -o $L/clark-flow.webp
python3 tools/build_report_card.py --out /tmp/rc.png && sips -Z 1400 /tmp/rc.png >/dev/null \
  && cwebp -q 86 /tmp/rc.png -o $L/clark-report.webp
```

With the NAS originals, `bash deploy/stage-artifacts.sh` produces the
full-quality set (including the animated flow). Changes in `deploy/output/` show
up immediately; no restart is needed.

## Day-to-day

| Task | Command |
|------|---------|
| Bring the site up | `python serve.py` (the proxy and tunnel are already running) |
| Pick up `web/` or `src/` changes | restart `serve.py` (nothing to rebuild) |
| Restart the proxy (e.g. after rotating the password) | `launchctl kickstart -k gui/$(id -u)/com.enablesu.riverglyph-proxy` |
| Take the site offline | `launchctl bootout gui/$(id -u)/com.enablesu.riverglyph-tunnel` |
| Bring it back | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.enablesu.riverglyph-tunnel.plist` |
| Who's visiting | `tail -f ~/Library/Logs/riverglyph-proxy.log` |

To keep the Mac awake while plugged in, run `caffeinate -s` in a terminal, or
turn on *System Settings → Battery → Options → Prevent automatic sleeping when
the display is off*.

## Troubleshooting

- **Error 1033 / "Argo Tunnel error"**: the tunnel isn't running, or the Mac is
  asleep. Check `~/Library/Logs/riverglyph-tunnel.log` and
  `cloudflared tunnel info riverglyph`.
- **502 Bad Gateway from Cloudflare**: the tunnel is up but the proxy isn't.
  Check `~/Library/Logs/riverglyph-proxy.log`. If it says `refusing to start`,
  `deploy/riverglyph.env` is missing or empty.
- **"riverglyph app is not running"**: start `python serve.py`.
- **Login prompt keeps reappearing**: wrong passphrase. Remember the user is the
  same phrase as the password. Browsers cache Basic Auth per session; use a
  private window to retest.
- **mobile-prep breaks after you work on this**: something started `bridge-james`
  on this Mac. Run `pgrep -fl cloudflared`; the only cloudflared process here
  should include `--config …/riverglyph.yml`.

## Teardown

```bash
bash deploy/install-riverglyph.sh uninstall
cloudflared tunnel delete riverglyph   # permanent; then delete the riverglyph CNAME in the Cloudflare dashboard
```

## Notes

- **Alternative: static demo container.** `deploy/docker-compose.riverglyph.yml`
  runs the NAS-staged static demo (no backend) behind `deploy/auth_server.py` on
  the same port 8081. To switch to it, boot out the proxy LaunchAgent first, since
  only one can hold 8081. It needs `deploy/stage-artifacts.sh` (NAS mounted) for
  its images.
- Basic Auth is a simple shared gate. For per-person logins or revocation, use
  Cloudflare Zero Trust **Access** (email one-time PIN) on this hostname instead.
  It needs no code changes.
- Stripe webhooks can't reach `/api/webhook/stripe` through Basic Auth. If you
  wire Stripe up later, that route needs its own exemption.
