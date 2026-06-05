#!/usr/bin/env bash
# Deploy Team 12 live demo to AWS EC2 (temporary hackathon instance)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGION="${AWS_REGION:-us-east-1}"
KEY_NAME="${EC2_KEY_NAME:-pax-ec2-key}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/pax-ec2-key.pem}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
TAG_NAME="team12-hackathon"
PORT=8787

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — run: python3 scripts/setup_env.py" >&2
  exit 1
fi
if [[ ! -f "$SSH_KEY" ]]; then
  echo "Missing SSH key: $SSH_KEY" >&2
  exit 1
fi

echo "==> Resolve Ubuntu 22.04 AMI"
AMI=$(aws ec2 describe-images --region "$REGION" --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)

echo "==> Security group (port $PORT)"
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=group-name,Values=team12-hackathon-sg" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
  SG_ID=$(aws ec2 create-security-group --region "$REGION" \
    --group-name team12-hackathon-sg \
    --description "Team 12 hackathon demo port $PORT" \
    --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
    --protocol tcp --port "$PORT" --cidr 0.0.0.0/0
  aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
    --protocol tcp --port 22 --cidr 0.0.0.0/0
fi

echo "==> Find or launch instance"
INSTANCE_ID=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=$TAG_NAME" "Name=instance-state-name,Values=running,pending,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)

if [[ "$INSTANCE_ID" == "None" || -z "$INSTANCE_ID" ]]; then
  INSTANCE_ID=$(aws ec2 run-instances --region "$REGION" \
    --image-id "$AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME},{Key=Project,Value=hackathon}]" \
    --user-data "file://$ROOT/deploy/aws/bootstrap.sh" \
    --query Instances[0].InstanceId --output text)
  echo "Launched $INSTANCE_ID"
else
  STATE=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].State.Name' --output text)
  if [[ "$STATE" == "stopped" ]]; then
    aws ec2 start-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
  fi
  echo "Using existing $INSTANCE_ID"
fi

echo "==> Wait for running + status checks"
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-status-ok --region "$REGION" --instance-ids "$INSTANCE_ID" || sleep 30

PUBLIC_IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "==> Wait for SSH ($PUBLIC_IP)"
for i in $(seq 1 30); do
  if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@"$PUBLIC_IP" "echo ok" 2>/dev/null; then
    break
  fi
  sleep 10
done

echo "==> Sync repo"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" "mkdir -p /opt/team12"
rsync -az --delete \
  --exclude '.git' --exclude '.env' --exclude 'data/.token' --exclude '__pycache__' \
  -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
  "$ROOT/" "ubuntu@$PUBLIC_IP:/opt/team12/team12-2402ndave/"

echo "==> Upload .env (server-side only)"
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROOT/.env" "ubuntu@$PUBLIC_IP:/opt/team12/team12-2402ndave/.env"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" "chmod 600 /opt/team12/team12-2402ndave/.env"

echo "==> Install systemd unit + hydrate + start"
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$ROOT/deploy/aws/bootstrap.sh" "ubuntu@$PUBLIC_IP:/tmp/bootstrap.sh"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" "sudo bash /tmp/bootstrap.sh"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ubuntu@"$PUBLIC_IP" \
  "cd /opt/team12/team12-2402ndave && python3 scripts/enrich_public.py && sudo systemctl restart team12-api"

echo "==> Health check"
for i in $(seq 1 20); do
  if curl -sf "http://$PUBLIC_IP:$PORT/api/health" >/dev/null 2>&1; then
    echo "LIVE: http://$PUBLIC_IP:$PORT/cover.html"
    echo "$PUBLIC_IP" > "$ROOT/deploy/aws/LIVE_HOST.txt"
    exit 0
  fi
  sleep 5
done

echo "Deploy finished but health check pending. Try: curl http://$PUBLIC_IP:$PORT/api/health" >&2
echo "$PUBLIC_IP" > "$ROOT/deploy/aws/LIVE_HOST.txt"
exit 1
