# Atlas Core — run your Atlas sync as a scheduled AWS Lambda (container image).
#
# A container-image Lambda (not zip) lets you pull native deps (e.g. a SQL driver)
# cleanly. The SAME image can run the one-time full backfill (entrypoint override)
# and the scheduled incremental delta, so the two never drift.
#
#   # build (context = repo root):
#   docker build -f deploy/Dockerfile -t atlas-sync .
#
#   # one-time full backfill with the same image (entrypoint = your job directly):
#   docker run --rm --entrypoint python \
#     -e SOURCE_DSN -e ATLAS_PG_DSN -e COURSE_LIMIT=0 \
#     -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
#     atlas-sync /var/task/sync_job.py
#
FROM public.ecr.aws/lambda/python:3.12

# The engine + the extras you need (bedrock = Titan/Claude, postgres = pgvector,
# mssql = SQL Server source). Trim these to what your ingester actually uses.
COPY pyproject.toml README.md ${LAMBDA_TASK_ROOT}/src/
COPY atlas_core ${LAMBDA_TASK_ROOT}/src/atlas_core
RUN python -m pip install --no-cache-dir "${LAMBDA_TASK_ROOT}/src[bedrock,postgres,mssql]"

# YOUR ingest job + the thin Lambda handler. `sync_job.py` is a template — edit its
# table mapping / DSNs to your schema (see deploy/sync_job.py and deploy/README.md).
COPY deploy/sync_job.py ${LAMBDA_TASK_ROOT}/sync_job.py
COPY deploy/handler.py  ${LAMBDA_TASK_ROOT}/handler.py

# Source files may be mode 600; COPY preserves perms and Lambda runs as a non-root
# user, so make the task root world-readable (a root-only container would not hit
# this, but the Lambda runtime would get PermissionError reading the handler).
RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}

ENV COURSE_LIMIT=0
CMD ["handler.handler"]
