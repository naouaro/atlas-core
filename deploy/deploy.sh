#!/usr/bin/env bash
# Deploy an Atlas sync as a scheduled job: ECR image → Lambda → EventBridge schedule.
# Idempotent: safe to re-run (creates or updates). Secrets come from SSM, never this file.
#
# Prereqs (export before running):
#   - AWS_PROFILE / credentials with rights to ECR, Lambda, IAM, EventBridge Scheduler, SSM
#     (+ EC2/VPC if you run the Lambda inside a VPC).
#   - DSNs stored as SSM SecureString:
#       aws ssm put-parameter --name /atlas/source_dsn --type SecureString --value '...'
#       aws ssm put-parameter --name /atlas/pg_dsn     --type SecureString --value 'postgresql://...'
#   - Bedrock reachable from wherever the Lambda runs (a non-VPC Lambda uses the default
#     internet route; a VPC Lambda needs a NAT gateway or a bedrock-runtime VPC endpoint).
set -euo pipefail

# ---- config (override via env) ----------------------------------------------
REGION="${REGION:?set REGION=eu-west-1}"
BEDROCK_REGION="${BEDROCK_REGION:-us-east-1}"
FUNC="${FUNC:-atlas-sync}"
REPO="${REPO:-atlas-sync}"
SCHEDULE="${SCHEDULE:-rate(1 hour)}"
MEMORY="${MEMORY:-3008}"            # clustering the full map is memory-heavy at scale
TIMEOUT="${TIMEOUT:-900}"           # 15 min hard ceiling
SOURCE_SSM="${SOURCE_SSM:-/atlas/source_dsn}"
PG_SSM="${PG_SSM:-/atlas/pg_dsn}"
TENANT="${TENANT:-default}"
ROLE="${ROLE:-${FUNC}-role}"
# Optional VPC: set BOTH to run inside a VPC (must reach source + pgvector + Bedrock).
SUBNETS="${SUBNETS:-}"
SECURITY_GROUP="${SECURITY_GROUP:-}"

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
IMG="${ECR}/${REPO}:latest"
HERE="$(cd "$(dirname "$0")/.." && pwd)"   # repo root (build context)
echo "account=$ACCOUNT region=$REGION func=$FUNC image=$IMG"

# ---- 1. build + push image --------------------------------------------------
aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR"
docker build -f "$HERE/deploy/Dockerfile" -t "$IMG" "$HERE"
docker push "$IMG"

# ---- 2. IAM role (lambda + logs + bedrock + ssm read [+ VPC ENIs]) ----------
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version":"2012-10-17","Statement":[{"Effect":"Allow",
    "Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  [ -n "$SUBNETS" ] && aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole || true
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name atlas-inline --policy-document "{
  \"Version\":\"2012-10-17\",\"Statement\":[
    {\"Effect\":\"Allow\",\"Action\":[\"bedrock:InvokeModel\"],\"Resource\":\"*\"},
    {\"Effect\":\"Allow\",\"Action\":[\"ssm:GetParameter\"],\"Resource\":[
       \"arn:aws:ssm:${REGION}:${ACCOUNT}:parameter${SOURCE_SSM}\",
       \"arn:aws:ssm:${REGION}:${ACCOUNT}:parameter${PG_SSM}\"]}]}"
ROLE_ARN="$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)"

# ---- 3. resolve secrets from SSM (not persisted anywhere) -------------------
SOURCE_DSN="$(aws ssm get-parameter --name "$SOURCE_SSM" --with-decryption --query Parameter.Value --output text --region "$REGION")"
ATLAS_PG_DSN="$(aws ssm get-parameter --name "$PG_SSM"  --with-decryption --query Parameter.Value --output text --region "$REGION")"
ENV_JSON="{Variables={SOURCE_DSN=${SOURCE_DSN},ATLAS_PG_DSN=${ATLAS_PG_DSN},ATLAS_TENANT=${TENANT},COURSE_LIMIT=0,AWS_REGION=${BEDROCK_REGION}}}"
VPC_ARG=""
[ -n "$SUBNETS" ] && [ -n "$SECURITY_GROUP" ] && VPC_ARG="--vpc-config SubnetIds=${SUBNETS},SecurityGroupIds=${SECURITY_GROUP}"

# ---- 4. create/update the function ------------------------------------------
if aws lambda get-function --function-name "$FUNC" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNC" --image-uri "$IMG" --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNC" --region "$REGION"
  aws lambda update-function-configuration --function-name "$FUNC" --region "$REGION" \
    --timeout "$TIMEOUT" --memory-size "$MEMORY" --environment "$ENV_JSON" $VPC_ARG >/dev/null
else
  aws lambda create-function --function-name "$FUNC" --region "$REGION" \
    --package-type Image --code "ImageUri=${IMG}" --role "$ROLE_ARN" \
    --timeout "$TIMEOUT" --memory-size "$MEMORY" --environment "$ENV_JSON" $VPC_ARG >/dev/null
fi
aws lambda wait function-updated --function-name "$FUNC" --region "$REGION"
FUNC_ARN="$(aws lambda get-function --function-name "$FUNC" --query Configuration.FunctionArn --output text --region "$REGION")"

# ---- 5. EventBridge Scheduler → invoke the Lambda ---------------------------
SCHED_ROLE="${ROLE}-sched"
if ! aws iam get-role --role-name "$SCHED_ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$SCHED_ROLE" --assume-role-policy-document '{
    "Version":"2012-10-17","Statement":[{"Effect":"Allow",
    "Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
fi
aws iam put-role-policy --role-name "$SCHED_ROLE" --policy-name invoke --policy-document "{
  \"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",
  \"Action\":\"lambda:InvokeFunction\",\"Resource\":\"${FUNC_ARN}\"}]}"
SCHED_ROLE_ARN="$(aws iam get-role --role-name "$SCHED_ROLE" --query Role.Arn --output text)"

aws scheduler get-schedule --name "$FUNC" --region "$REGION" >/dev/null 2>&1 && OP=update-schedule || OP=create-schedule
aws scheduler $OP --name "$FUNC" --region "$REGION" \
  --schedule-expression "$SCHEDULE" --flexible-time-window '{"Mode":"OFF"}' \
  --target "{\"Arn\":\"${FUNC_ARN}\",\"RoleArn\":\"${SCHED_ROLE_ARN}\"}" >/dev/null

echo "done. scheduled '$SCHEDULE' → $FUNC. Test now:  aws lambda invoke --function-name $FUNC --region $REGION /dev/stdout"
