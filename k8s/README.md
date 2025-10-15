This folder contains Kubernetes manifests for the crypto-dashboard app.

Files included:
- backend-deployment.yml        Deployment for the backend (image: aditya19joshi01/crypto-backend:v1)
- backend-service.yml           ClusterIP service for the backend (port 8000)
- frontend-deployment.yml       Deployment for the frontend (image: aditya19joshi01/crypto-frontend:v1)
- frontend-service.yml          LoadBalancer service for the frontend (exposes port 80 -> container 3000)
- redis-deployment.yml          Redis Deployment (image: redis:7)
- redis-service.yml             ClusterIP service for Redis (port 6379)
- postgres-deployment.yml       Postgres Deployment (image: postgres:15) with a PVC mount
- postgres-service.yml          ClusterIP service for Postgres (port 5432)
- pgdata-pvc.yml                PersistentVolumeClaim for Postgres data (1Gi)
- secrets.yml                   Example Secret (base64 placeholders) for DB and Redis credentials

How to apply
1. Update `secrets.yml` with real base64-encoded values or create the secret directly with kubectl:
   kubectl create secret generic crypto-secrets \
     --from-literal=POSTGRES_USER=crypto \
     --from-literal=POSTGRES_PASSWORD=crypto \
     --from-literal=POSTGRES_DB=cryptodb \
     --from-literal=DATABASE_URL='postgresql://crypto:crypto@crypto-postgres:5432/cryptodb' \
     --from-literal=REDIS_URL='redis://crypto-redis:6379/0'

2. Apply manifests (order is not strict but PVC & Secret should exist before Postgres starts):
   kubectl apply -f secrets.yml
   kubectl apply -f pgdata-pvc.yml
   kubectl apply -f postgres-deployment.yml -f postgres-service.yml
   kubectl apply -f redis-deployment.yml -f redis-service.yml
   kubectl apply -f backend-deployment.yml -f backend-service.yml
   kubectl apply -f frontend-deployment.yml -f frontend-service.yml

Notes
- The frontend service is a LoadBalancer type for easy access in managed clusters. For local clusters like minikube or Docker Desktop, use `minikube service` or `kubectl port-forward` to reach the frontend.
- Adjust PVC `storageClassName` and size in `pgdata-pvc.yml` to match your cluster.
- Update image tags in `backend-deployment.yml` and `frontend-deployment.yml` to the tags you pushed to Docker Hub.
- Consider using Kustomize or Helm for more advanced deployments and environment-specific overrides.
