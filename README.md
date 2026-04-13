# SoundSentinel

SoundSentinel is a self-hosted audio monitoring MVP focused on DevOps practice.

In this first phase, the repository includes:

- a minimal FastAPI application
- a basic web dashboard
- health and readiness endpoints
- initial PostgreSQL wiring
- Docker files for local development
- the first Kubernetes scaffolding

The second phase now adds:

- a first audio ingestion endpoint
- upload validation rules
- basic database persistence for device and ingestion metadata
- WAV intensity metrics for each accepted upload
- behavior-based alerts from the evolving sound curve
- Telegram delivery attempts recorded for each alert
- an operational dashboard with device, sample, alert, and delivery visibility
- a first deployable infrastructure layer for Docker and single-node K3s

## Why this phase exists

Before we process real audio, we need a clean foundation:

- one repository with clear responsibilities
- one app that can boot reliably
- configuration handled through environment variables
- a database connection strategy that works locally and later in Kubernetes

That foundation will make the next phases much easier to build and debug.

## Project layout

```text
soundsentinel/
├── app/
├── tests/
├── scripts/
├── infra/
├── .github/workflows/
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── README.md
```

## Local development

1. Copy the example environment file:

   ```bash
   cp infra/env/.env.example .env
   ```

   The variables use the `SOUNDSENTINEL_` prefix on purpose so the project does not
   collide with generic shell variables such as `DEBUG`.

2. Start the local stack:

   ```bash
   docker compose up --build
   ```

3. Open the app:

   - Dashboard: `http://localhost:8000/`
   - Health: `http://localhost:8000/health`
   - Readiness: `http://localhost:8000/health/ready`

## What is ready now

- the application starts
- configuration is loaded from environment variables
- PostgreSQL connection settings are centralized
- the app can expose operational health endpoints
- the app can accept a small audio upload and register its metadata

## Audio ingestion in Phase 2

The endpoint below accepts one audio fragment, computes basic intensity
metrics, and stores both the ingestion metadata and the first sound sample.

```bash
curl -X POST http://localhost:8000/api/v1/audio/ingestions \
  -F "device_key=living-room-phone" \
  -F "captured_at=2026-04-13T09:45:00Z" \
  -F "audio_file=@sample.wav;type=audio/wav"
```

Accepted formats for the current MVP:

- `audio/wav`
- `audio/x-wav`

Why only WAV for now:

- it keeps the pipeline simple and reliable
- Python can process PCM WAV with the standard library
- we avoid introducing `ffmpeg` until it is really needed

Current upload limit:

- `2,000,000` bytes

Metrics computed in the current phase:

- `duration_seconds`
- `sample_rate_hz`
- `channel_count`
- `rms_amplitude`
- `peak_amplitude`
- `normalized_rms`
- `normalized_peak`

Behavior rules added in this phase:

- `spike_peak`: a single sample exceeds the configured peak threshold
- `sustained_noise`: the average RMS stays high across a recent time window
- `repeated_peaks`: several peaks happen inside a short window

Default rule values:

- `SOUNDSENTINEL_SPIKE_PEAK_THRESHOLD=0.8`
- `SOUNDSENTINEL_SUSTAINED_NOISE_THRESHOLD=0.2`
- `SOUNDSENTINEL_SUSTAINED_NOISE_WINDOW_SECONDS=1`
- `SOUNDSENTINEL_REPEATED_PEAK_THRESHOLD=0.55`
- `SOUNDSENTINEL_REPEATED_PEAK_WINDOW_SECONDS=2`
- `SOUNDSENTINEL_REPEATED_PEAK_MIN_COUNT=3`
- `SOUNDSENTINEL_ALERT_COOLDOWN_SECONDS=60`

Alert delivery in this phase:

- alerts are attempted through Telegram
- if Telegram is not configured, the system records the delivery as `skipped`
- if Telegram is configured but the request fails, the delivery is stored as `failed`
- successful sends are stored as `sent`

Operational dashboard in this phase:

- sensor status based on `last_seen_at`
- recent sound samples
- recent alerts
- recent notification deliveries

Infrastructure and operations in this phase:

- container healthchecks for local runtime
- restart policies in `docker compose`
- Kubernetes manifests for a single-node K3s VPS
- CI/CD that tests the code, publishes the container image to GHCR, and can deploy to the VPS
- helper scripts to install K3s and deploy to a VPS over SSH

## What comes next

- richer dashboards over time
- configurable rules per device

## Real VPS Deployment

This repository now includes a simple path for a single VPS deployment:

1. Install K3s on the VPS with `scripts/install_k3s_server.sh`
2. Build and publish your Docker image
3. Deploy over SSH with `scripts/deploy_single_vps.sh`

See [infra/k8s/README.md](infra/k8s/README.md) for the exact sequence and examples.

## GitHub Actions Deployment

Once your manual VPS deployment works, you can automate the next releases through
GitHub Actions.

What the workflow does:

- runs tests on pull requests and pushes
- builds a Linux `amd64` image for the VPS
- pushes the image to `ghcr.io`
- deploys the new image to the K3s VPS on `main`

### Required GitHub secrets

Add these repository secrets in GitHub:

- `VPS_HOST`: your VPS IP, for example `152.228.129.240`
- `VPS_USER`: your SSH user, for example `ubuntu`
- `VPS_SSH_PRIVATE_KEY`: the private SSH key used by GitHub Actions
- `SOUNDSENTINEL_POSTGRES_PASSWORD`: PostgreSQL password for production
- `SOUNDSENTINEL_TELEGRAM_BOT_TOKEN`: Telegram bot token
- `SOUNDSENTINEL_TELEGRAM_CHAT_ID`: Telegram chat ID

Optional:

- `SOUNDSENTINEL_PUBLIC_HOST`: domain name if you later stop using the raw VPS IP

### Recommended SSH setup for GitHub Actions

1. Create a dedicated deploy key on your Mac:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/soundsentinel_actions -C "soundsentinel-actions"
   ```

2. Copy the public key:

   ```bash
   cat ~/.ssh/soundsentinel_actions.pub
   ```

3. Add that public key to the VPS user:

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   nano ~/.ssh/authorized_keys
   ```

   Paste the public key on its own line, save, and then run:

   ```bash
   chmod 600 ~/.ssh/authorized_keys
   ```

4. Copy the private key from:

   ```bash
   cat ~/.ssh/soundsentinel_actions
   ```

   Save that full private key as the GitHub secret `VPS_SSH_PRIVATE_KEY`.

### First automated release

After the secrets are configured:

1. Push your code to GitHub
2. Merge or push to `main`
3. Open the `Actions` tab in GitHub
4. Watch the `CI/CD` workflow complete

If the workflow passes, GitHub will publish the image and redeploy the VPS
automatically.
