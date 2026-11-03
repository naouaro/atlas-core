# Deploy Atlas as a scheduled sync (EventBridge → Lambda)

Keep your Atlas map live: a scheduled job re-runs your ingester on a cadence, and
`atlas.sync()` re-embeds only what changed. **One image, two jobs** — the Lambda and
the one-time backfill run the *same* `run()`, so they never drift.

## Shape

```
EventBridge Scheduler ──rate(1 hour)──▶ Lambda (container image)
                                          └─ sync_job.run()
   source DB (read-only) ──▶ embeddings (Titan) ──▶ pgvector store
```

A container-image Lambda (not zip) keeps native source drivers simple. "Sync takes
hours" is the **first full backfill only** — run it once; every scheduled run after is
a fast delta that fits the 15-min ceiling.

## 1. Write your job

Copy `sync_job.py` and edit the table/link mapping to your schema (and the source
driver if you are not on SQL Server). The handler just calls its `run()`.

## 2. One-time full backfill (run once)

```bash
docker build -f deploy/Dockerfile -t atlas-sync .
docker run --rm --entrypoint python \
  -e SOURCE_DSN='...' -e ATLAS_PG_DSN='postgresql://...:5432/atlas' \
  -e ATLAS_TENANT=my_workspace -e COURSE_LIMIT=0 \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION=us-east-1 \
  atlas-sync /var/task/sync_job.py
```

## 3. Stand up the scheduled delta

```bash
# store secrets once (SecureString — never in code):
aws ssm put-parameter --name /atlas/source_dsn --type SecureString --value '...'
aws ssm put-parameter --name /atlas/pg_dsn     --type SecureString --value 'postgresql://...'

# then deploy (idempotent):
REGION=eu-west-1 FUNC=atlas-sync TENANT=my_workspace SCHEDULE='rate(1 hour)' \
  ./deploy/deploy.sh
```

Run non-VPC (simplest — uses the default internet route to reach Bedrock and a
publicly-reachable DB) **or** inside a VPC by setting `SUBNETS=` and `SECURITY_GROUP=`.

## Knobs
`REGION` (required), `FUNC`/`REPO` (`atlas-sync`), `TENANT` (`default`),
`SCHEDULE` (`rate(1 hour)`), `MEMORY` (`3008` — raise it if clustering a large map
OOMs), `TIMEOUT` (`900`), `BEDROCK_REGION` (`us-east-1`), `SOURCE_SSM`/`PG_SSM`,
`SUBNETS`/`SECURITY_GROUP` (optional VPC).

## Networking notes
- Non-VPC Lambda: reaches Bedrock + a public DB endpoint over the default route.
- VPC Lambda: has **no default internet route** → Bedrock needs a NAT gateway or a
  `com.amazonaws.<region>.bedrock-runtime` interface endpoint; the subnets + SG must
  reach the source DB and pgvector on 5432.
- If your DB SG is open to `0.0.0.0/0`, tighten it to the Lambda SG (or a bastion/your
  IP) — don't leave `5432` open to the world.
