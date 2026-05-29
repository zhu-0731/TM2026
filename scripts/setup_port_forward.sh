#!/usr/bin/env bash
# Start port-forwards for Prometheus and Online Boutique frontend.
# Run this in a separate terminal and keep it alive during data collection.
set -euo pipefail

export DOCKER_HOST="npipe:////./pipe/docker_engine"

# Git Bash on Windows may pick up WSL kubectl instead of kubectl.exe.
# Force the Windows binary and set KUBECONFIG to the Windows-style path.
if command -v kubectl.exe &>/dev/null; then
    KUBECTL="kubectl.exe"
else
    KUBECTL="kubectl"
fi
export KUBECONFIG="${HOME}/.kube/config"

echo "Updating kubeconfig ..."
minikube update-context 2>/dev/null || true

echo "Verifying cluster is reachable ..."
if ! "$KUBECTL" get nodes --request-timeout=10s &>/dev/null; then
    echo "ERROR: Cannot reach Kubernetes cluster."
    echo "  kubectl binary: $(command -v $KUBECTL)"
    echo "  KUBECONFIG:     $KUBECONFIG"
    echo "  Run in PowerShell: minikube start"
    exit 1
fi
echo "Cluster OK"
echo ""

echo "Starting port-forward: Prometheus  istio-system:9090  -> localhost:9090"
"$KUBECTL" port-forward -n istio-system svc/prometheus 9090:9090 &
PF_PROM_PID=$!

echo "Starting port-forward: Online Boutique frontend:80   -> localhost:8080"
"$KUBECTL" port-forward -n online-boutique svc/frontend 8080:80 &
PF_FRONT_PID=$!

echo "Starting port-forward: Grafana  monitoring:80  -> localhost:3000"
"$KUBECTL" port-forward -n monitoring svc/grafana 3000:80 &
PF_GRAF_PID=$!

echo ""
echo "Port-forwards active:"
echo "  Prometheus:      http://localhost:9090"
echo "  Online Boutique: http://localhost:8080"
echo "  Grafana:         http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all port-forwards."

trap "kill $PF_PROM_PID $PF_FRONT_PID $PF_GRAF_PID 2>/dev/null; echo 'Port-forwards stopped.'" EXIT
wait
