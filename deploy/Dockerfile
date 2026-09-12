# Static demo image for the hydro-art web control surface.
#
# Deliberately GDAL-free and tiny: it serves the self-contained web/ pages. The
# two pre-rendered display SVGs the viewer pages fetch are bind-mounted read-only
# at runtime into /app/output (see deploy/README.md), keeping them out of the
# image. The tree is served from /app so each page's relative `../output/<name>.svg`
# fetch resolves. For LIVE pipeline renders you need a different, much heavier
# image (GDAL base + datasets/ volume) — see deploy/README.md.
FROM python:3.12-slim

WORKDIR /app

# The web control surface + the customer-facing landing page. (3d.html builds a
# WebGL model from the mounted SVGs; start.html uses absolute /web/... asset paths.)
COPY web/ ./web/

# Serve the customer landing at `/` — it's the first-touch page a visitor lands on.
RUN cp web/start.html index.html

EXPOSE 8080

# stdlib static server. Binds all interfaces INSIDE the container; the host and
# Tailscale control who can actually reach it (see deploy/README.md).
CMD ["python", "-m", "http.server", "8080", "--bind", "0.0.0.0"]
