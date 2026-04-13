#!/usr/bin/env sh

set -eu

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to install K3s."
  exit 1
fi

if command -v k3s >/dev/null 2>&1; then
  echo "K3s is already installed."
else
  echo "Installing K3s server..."
  curl -sfL https://get.k3s.io | sh -
fi

echo "Enabling and starting K3s..."
sudo systemctl enable k3s
sudo systemctl restart k3s

mkdir -p "$HOME/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
sudo chown "$(id -u)":"$(id -g)" "$HOME/.kube/config"
chmod 600 "$HOME/.kube/config"

echo
echo "K3s status:"
sudo systemctl --no-pager --full status k3s | sed -n '1,12p'
echo
echo "kubectl nodes:"
sudo k3s kubectl get nodes -o wide

