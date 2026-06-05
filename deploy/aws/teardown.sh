#!/usr/bin/env bash
# Terminate Team 12 hackathon EC2 after the event
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"
INSTANCE_ID="${1:-i-014a8df0209e951c7}"
echo "Terminating $INSTANCE_ID ..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
echo "Done. Rotate OpenAI + CA secrets after teardown."
