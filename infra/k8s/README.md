# Kubernetes Deployment

This folder contains a minimal Kubernetes deployment for a single-node K3s VPS.

## Files

- `namespace.yaml`: isolates the app resources
- `app-configmap.yaml`: non-sensitive runtime configuration
- `app-secret.yaml`: application secrets such as database credentials and Telegram
- `postgres-secret.yaml`: PostgreSQL credentials
- `postgres-pvc.yaml`: persistent storage for PostgreSQL
- `postgres-deployment.yaml`: PostgreSQL workload
- `postgres-service.yaml`: stable internal PostgreSQL address
- `app-deployment.yaml`: SoundSentinel web/API workload
- `app-service.yaml`: stable internal app address
- `ingress.yaml`: external HTTP entrypoint through Traefik
- `kustomization.yaml`: apply everything in one command

## Before Applying

1. Edit `app-secret.yaml` and replace placeholder passwords.
2. Set your Telegram values if you want notifications in production.
3. Update `app-deployment.yaml` to use your real image name.
4. Update `ingress.yaml` with your real domain or subdomain if you have one.

## Apply

```bash
kubectl apply -k infra/k8s
```

## Verify

```bash
kubectl get pods -n soundsentinel
kubectl get svc -n soundsentinel
kubectl get ingress -n soundsentinel
kubectl logs deployment/soundsentinel-app -n soundsentinel
```

## Notes

- This setup is intentionally simple and uses a single PostgreSQL pod.
- It is good for learning and a first VPS deployment, not high availability.
- K3s already includes Traefik by default, which is why the ingress is minimal.
- If you do not have a domain yet, the deployment helper script can switch the ingress to a hostless rule so you can enter through the VPS IP.
- A cleanup CronJob runs daily and removes data older than the configured retention days.

## Helper Scripts

Run on the VPS itself:

```bash
./scripts/install_k3s_server.sh
```

Run from your local machine to deploy over SSH:

```bash
SOUNDSENTINEL_POSTGRES_PASSWORD='change-me' \
./scripts/deploy_single_vps.sh ubuntu@203.0.113.10 ghcr.io/acme/soundsentinel:latest
```

With a domain:

```bash
SOUNDSENTINEL_POSTGRES_PASSWORD='change-me' \
SOUNDSENTINEL_TELEGRAM_BOT_TOKEN='...' \
SOUNDSENTINEL_TELEGRAM_CHAT_ID='...' \
./scripts/deploy_single_vps.sh ubuntu@203.0.113.10 ghcr.io/acme/soundsentinel:latest soundsentinel.example.com
```

## Automated GitHub Actions Deploys

The repository workflow can also publish and deploy automatically after a push to
`main`.

### Required GitHub secrets

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_PRIVATE_KEY`
- `SOUNDSENTINEL_POSTGRES_PASSWORD`
- `SOUNDSENTINEL_TELEGRAM_BOT_TOKEN`
- `SOUNDSENTINEL_TELEGRAM_CHAT_ID`

Optional:

- `SOUNDSENTINEL_PUBLIC_HOST`

### Important notes

- The workflow pushes images to `ghcr.io/<owner>/soundsentinel`
- The deploy script waits for both `soundsentinel-postgres` and `soundsentinel-app`
  to become ready
- If you deploy by raw IP, leave `SOUNDSENTINEL_PUBLIC_HOST` empty so the helper
  script generates a hostless ingress rule
