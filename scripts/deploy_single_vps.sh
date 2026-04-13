#!/usr/bin/env sh

set -eu

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_single_vps.sh <ssh_target> <image_ref> [public_host]

Examples:
  ./scripts/deploy_single_vps.sh ubuntu@203.0.113.10 ghcr.io/acme/soundsentinel:latest
  ./scripts/deploy_single_vps.sh ubuntu@203.0.113.10 ghcr.io/acme/soundsentinel:latest soundsentinel.example.com

Required environment variables:
  SOUNDSENTINEL_POSTGRES_PASSWORD

Optional environment variables:
  SOUNDSENTINEL_POSTGRES_USER
  SOUNDSENTINEL_POSTGRES_DB
  SOUNDSENTINEL_TELEGRAM_BOT_TOKEN
  SOUNDSENTINEL_TELEGRAM_CHAT_ID
  SOUNDSENTINEL_SENSOR_ADMIN_TOKEN
EOF
}

if [ "${1:-}" = "" ] || [ "${2:-}" = "" ]; then
  usage
  exit 1
fi

if [ "${SOUNDSENTINEL_POSTGRES_PASSWORD:-}" = "" ]; then
  echo "SOUNDSENTINEL_POSTGRES_PASSWORD is required."
  exit 1
fi

SSH_TARGET="$1"
IMAGE_REF="$2"
PUBLIC_HOST="${3:-}"

POSTGRES_USER="${SOUNDSENTINEL_POSTGRES_USER:-soundsentinel}"
POSTGRES_DB="${SOUNDSENTINEL_POSTGRES_DB:-soundsentinel}"
TELEGRAM_BOT_TOKEN="${SOUNDSENTINEL_TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${SOUNDSENTINEL_TELEGRAM_CHAT_ID:-}"
SENSOR_ADMIN_TOKEN="${SOUNDSENTINEL_SENSOR_ADMIN_TOKEN:-}"

REMOTE_DIR="/tmp/soundsentinel-k8s"

echo "Copying Kubernetes manifests to ${SSH_TARGET}:${REMOTE_DIR}..."
ssh "$SSH_TARGET" "rm -rf ${REMOTE_DIR} && mkdir -p ${REMOTE_DIR}"
scp infra/k8s/*.yaml "$SSH_TARGET:${REMOTE_DIR}/"

echo "Preparing remote manifests..."
ssh "$SSH_TARGET" \
  "IMAGE_REF='$IMAGE_REF' \
   PUBLIC_HOST='$PUBLIC_HOST' \
   POSTGRES_USER='$POSTGRES_USER' \
   POSTGRES_PASSWORD='$SOUNDSENTINEL_POSTGRES_PASSWORD' \
   POSTGRES_DB='$POSTGRES_DB' \
   TELEGRAM_BOT_TOKEN='$TELEGRAM_BOT_TOKEN' \
   TELEGRAM_CHAT_ID='$TELEGRAM_CHAT_ID' \
   SENSOR_ADMIN_TOKEN='$SENSOR_ADMIN_TOKEN' \
   KUBECONFIG=\"\$HOME/.kube/config\" \
   REMOTE_DIR='$REMOTE_DIR' \
   sh -s" <<'EOF'
set -eu

cd "$REMOTE_DIR"
export KUBECONFIG="$HOME/.kube/config"

sed -i \
  -e "s|ghcr.io/your-org/soundsentinel:latest|$IMAGE_REF|g" \
  app-deployment.yaml

sed -i \
  -e "s|ghcr.io/your-org/soundsentinel:latest|$IMAGE_REF|g" \
  cleanup-cronjob.yaml

sed -i \
  -e "s|change-me|$POSTGRES_PASSWORD|g" \
  app-secret.yaml \
  postgres-secret.yaml

sed -i \
  -e "s|SOUNDSENTINEL_POSTGRES_USER: \"soundsentinel\"|SOUNDSENTINEL_POSTGRES_USER: \"$POSTGRES_USER\"|g" \
  -e "s|SOUNDSENTINEL_POSTGRES_DB: \"soundsentinel\"|SOUNDSENTINEL_POSTGRES_DB: \"$POSTGRES_DB\"|g" \
  app-configmap.yaml

sed -i \
  -e "s|POSTGRES_USER: \"soundsentinel\"|POSTGRES_USER: \"$POSTGRES_USER\"|g" \
  -e "s|POSTGRES_DB: \"soundsentinel\"|POSTGRES_DB: \"$POSTGRES_DB\"|g" \
  postgres-secret.yaml

sed -i \
  -e "s|SOUNDSENTINEL_TELEGRAM_BOT_TOKEN: \"\"|SOUNDSENTINEL_TELEGRAM_BOT_TOKEN: \"$TELEGRAM_BOT_TOKEN\"|g" \
  -e "s|SOUNDSENTINEL_TELEGRAM_CHAT_ID: \"\"|SOUNDSENTINEL_TELEGRAM_CHAT_ID: \"$TELEGRAM_CHAT_ID\"|g" \
  -e "s|SOUNDSENTINEL_SENSOR_ADMIN_TOKEN: \"\"|SOUNDSENTINEL_SENSOR_ADMIN_TOKEN: \"$SENSOR_ADMIN_TOKEN\"|g" \
  app-secret.yaml

if [ -n "$PUBLIC_HOST" ]; then
  sed -i -e "s|soundsentinel.example.com|$PUBLIC_HOST|g" ingress.yaml
else
  cat > ingress.yaml <<'INGRESS'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: soundsentinel
  namespace: soundsentinel
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: soundsentinel-app
                port:
                  number: 80
INGRESS
fi

echo "Applying manifests..."
kubectl apply -k "$REMOTE_DIR"

echo
echo "Waiting for workloads to become ready..."
kubectl rollout status deployment/soundsentinel-postgres -n soundsentinel --timeout=180s
kubectl rollout status deployment/soundsentinel-app -n soundsentinel --timeout=180s

echo
echo "Deployment summary:"
kubectl get pods -n soundsentinel
echo
kubectl get svc -n soundsentinel
echo
kubectl get ingress -n soundsentinel
EOF

echo
echo "Done."
if [ -n "$PUBLIC_HOST" ]; then
  echo "Try opening: http://$PUBLIC_HOST"
else
  echo "Try opening your VPS public IP in the browser: http://<your-vps-ip>"
fi
