#!/usr/bin/env bash
set -euo pipefail

# Upload MU Jan/Feb bundle to Cloudflare R2 using Wrangler (no S3 key pair required).
# Preconditions:
# - Wrangler login already completed.
# - Bucket exists and public dev URL is enabled.
#
# Required env vars:
#   R2_ACCOUNT_ID
#   R2_BUCKET
#   R2_PUBLIC_BASE_URL
#
# Optional env vars:
#   R2_PREFIX            (default: mu)
#   WRANGLER_VERSION     (default: 4.65.0)

if [[ -z "${R2_ACCOUNT_ID:-}" ]]; then
  echo "Missing R2_ACCOUNT_ID" >&2
  exit 1
fi
if [[ -z "${R2_BUCKET:-}" ]]; then
  echo "Missing R2_BUCKET" >&2
  exit 1
fi
if [[ -z "${R2_PUBLIC_BASE_URL:-}" ]]; then
  echo "Missing R2_PUBLIC_BASE_URL" >&2
  exit 1
fi

R2_PREFIX="${R2_PREFIX:-mu}"
WRANGLER_VERSION="${WRANGLER_VERSION:-4.65.0}"
STAGE_DIR="/tmp/mu_r2_publish_stage"

wr() {
  npx -y "wrangler@${WRANGLER_VERSION}" "$@"
}

echo "Preparing MU Jan/Feb stage and public manifest..."
R2_DRY_RUN=1 \
R2_MANIFEST_MODE=public \
R2_ACCOUNT_ID="${R2_ACCOUNT_ID}" \
R2_BUCKET="${R2_BUCKET}" \
R2_PUBLIC_BASE_URL="${R2_PUBLIC_BASE_URL}" \
R2_PREFIX="${R2_PREFIX}" \
python3 scripts/publish_mu_r2_janfeb.py

if [[ ! -d "${STAGE_DIR}/mu" ]]; then
  echo "Stage directory missing: ${STAGE_DIR}/mu" >&2
  exit 1
fi

echo "Uploading data objects to r2://${R2_BUCKET}/${R2_PREFIX}/ ..."
count=0
while IFS= read -r -d '' file; do
  rel="${file#"${STAGE_DIR}/"}"
  case "${file}" in
    *.csv) ct="text/csv" ;;
    *.parquet) ct="application/octet-stream" ;;
    *) ct="application/octet-stream" ;;
  esac

  wr r2 object put "${R2_BUCKET}/${rel}" --remote --file "${file}" --content-type "${ct}" >/dev/null
  count=$((count + 1))
  echo "uploaded ${count}: ${rel}"
done < <(find "${STAGE_DIR}/mu" -type f -print0 | sort -z)

echo "Uploading manifest..."
wr r2 object put \
  "${R2_BUCKET}/${R2_PREFIX}/manifests/mu_janfeb_manifest.json" \
  --remote \
  --file "${STAGE_DIR}/mu_janfeb_manifest.json" \
  --content-type "application/json" \
  >/dev/null

echo "Done."
echo "Manifest URL: ${R2_PUBLIC_BASE_URL}/${R2_PREFIX}/manifests/mu_janfeb_manifest.json"
