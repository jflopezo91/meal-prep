#!/usr/bin/env bash
# Release the meal-prep app to the NAS from the workstation. Never builds: it only approves the image
# GitHub built and attested for the current commit of main, then deploys it by digest over SSH.
#
#   scripts/release.sh                 gate, backup, deploy, health check, then tag vYYYY.MM.DD[.N]
#   scripts/release.sh --dry-run       gate only: prints the digest and tag, changes nothing
#   scripts/release.sh --rollback TAG  redeploy an earlier release (with a backup first)
#
# The release record is the annotated tag; nothing is committed to main. Procedures: docs/DEPLOYMENT.md.
set -euo pipefail

NAS="${MEAL_PREP_NAS:-nas-user@<wifi-ip>}"
DIR="${MEAL_PREP_NAS_DIR:-/volume1/docker/meal-prep}"
REPO=jflopezo91/meal-prep
IMAGE="ghcr.io/$REPO"
WORKFLOW=.github/workflows/container.yml
HOST="${NAS#*@}"
HEALTH_WAIT=180  # seconds

die() { printf 'REFUSED: %s\n' "$*" >&2; exit 1; }
say() { printf '==> %s\n' "$*"; }
remote() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS" "$@"; }

verify_attestation() {  # digest commit
    gh attestation verify "oci://$IMAGE@$1" --repo "$REPO" \
        --signer-workflow "$REPO/$WORKFLOW" --source-digest "$2" >/dev/null \
        || die "attestation check failed for $1 (commit $2)"
}

resolve_digest() {  # commit
    local token digest
    token=$(curl -fsS -m 20 "https://ghcr.io/token?scope=repository:$REPO:pull" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])') \
        || die "cannot get a GHCR token"
    digest=$(curl -fsSI -m 20 -H "Authorization: Bearer $token" \
        -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json' \
        "https://ghcr.io/v2/$REPO/manifests/sha-$1" \
        | tr -d '\r' | awk 'tolower($1) == "docker-content-digest:" { print $2 }') \
        || die "no image in GHCR for commit $1"
    [[ $digest == sha256:* ]] || die "no image digest in GHCR for commit $1"
    printf '%s\n' "$digest"
}

gate() {
    local branch ci
    command -v gh >/dev/null || die "gh is not installed"
    gh attestation verify --help >/dev/null 2>&1 || die "this gh has no 'attestation' command; upgrade it"
    branch=$(git symbolic-ref --short -q HEAD || true)
    [[ $branch == main ]] || die "not on main (on '${branch:-detached HEAD}')"
    [[ -z $(git status --porcelain) ]] || die "the working tree is not clean"
    git fetch -q --tags origin main
    commit=$(git rev-parse HEAD)
    [[ $commit == "$(git rev-parse origin/main)" ]] || die "HEAD is not origin/main; push or pull first"
    ci=$(gh run list --repo "$REPO" --workflow container.yml --commit "$commit" --branch main --limit 1 \
        --json status,conclusion --jq '.[0] | "\(.status)/\(.conclusion)"')
    [[ $ci == completed/success ]] || die "CI for ${commit:0:7} is not green (${ci:-no run found})"
    digest=$(resolve_digest "$commit")
    verify_attestation "$digest" "$commit"
    say "gate passed: ${commit:0:7} = $digest"
}

next_tag() {
    local existing day n
    existing=$(git tag --points-at "$commit" 'v[0-9]*' | sort -V | tail -n 1)
    if [[ -n $existing ]]; then printf '%s\n' "$existing"; return; fi
    day=v$(TZ=America/Bogota date +%Y.%m.%d)
    if ! git rev-parse -q --verify "refs/tags/$day" >/dev/null; then printf '%s\n' "$day"; return; fi
    n=2
    while git rev-parse -q --verify "refs/tags/$day.$n" >/dev/null; do n=$((n + 1)); done
    printf '%s\n' "$day.$n"
}

backup_first() {  # label; aborts the deploy when a backup that should exist cannot be taken
    local dest
    dest="/backups/pre-release/mealplanner-$(date -u +%Y%m%dT%H%M%SZ)-$1.db"
    remote "cd '$DIR'
        if [ ! -f .env ]; then echo 'first deploy: no release yet, nothing to back up'; exit 0; fi
        script='[ -f /data/mealplanner.db ] || { echo no database yet; exit 0; }
                mkdir -p /backups/pre-release
                backup-now.sh $dest && echo backup: $dest
                ls -1 /backups/pre-release/mealplanner-*.db | sort -r | tail -n +21 | xargs -r rm -f --'
        if [ \"\$(docker inspect -f '{{.State.Running}}' meal-prep-backup 2>/dev/null)\" = true ]; then
            docker exec meal-prep-backup sh -c \"\$script\"
        else
            docker compose run --rm --no-deps -T --entrypoint sh backup -c \"\$script\"
        fi"
}

deploy_steps() {  # digest commit
    git show "$2:deploy/docker-compose.yml" | remote "cat > '$DIR/compose.yaml.new'" || return 1
    remote "cd '$DIR'
        [ -f compose.yaml ] && cp compose.yaml compose.yaml.previous
        [ -f .env ] && cp .env .env.previous
        mv compose.yaml.new compose.yaml
        printf 'MEAL_PREP_DIGEST=%s\n' '$1' > .env
        docker compose pull -q && docker compose up -d" || return 1

    local waited=0 health=''
    while (( waited < HEALTH_WAIT )); do
        health=$(remote "docker inspect -f '{{.State.Health.Status}}' meal-prep" 2>/dev/null || true)
        [[ $health == healthy ]] && break
        sleep 5; waited=$((waited + 5))
    done
    [[ $health == healthy ]] || { echo "container not healthy after ${HEALTH_WAIT}s ($health)" >&2; return 1; }

    local running
    running=$(remote "docker exec meal-prep printenv MEALPLANNER_APP_REVISION")
    [[ $running == "$2" ]] || { echo "running revision is '$running', expected $2" >&2; return 1; }
    curl -fsS -m 10 -o /dev/null "http://$HOST:8080/healthz" \
        || { echo "http://$HOST:8080/healthz does not answer from here" >&2; return 1; }
}

undo_deploy() {
    echo "Deploy failed; going back to the previous release." >&2
    remote "cd '$DIR'
        if [ -f .env.previous ]; then
            cp .env.previous .env; cp compose.yaml.previous compose.yaml; docker compose up -d
        else
            echo 'No previous release to return to; containers left as they are.'
        fi" || echo "Could not restore the previous release; see docs/DEPLOYMENT.md." >&2
}

deploy() {  # digest commit label
    backup_first "$3" || die "backup failed; nothing was deployed"
    say "deploying $3 ($1)"
    if ! deploy_steps "$1" "$2"; then
        undo_deploy
        exit 1
    fi
    say "healthy on ${2:0:7}: http://$HOST:8080/"
}

case "${1:-}" in
    --help|-h) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --dry-run)
        gate
        say "would release as $(next_tag) to $NAS:$DIR (dry run: nothing changed)"
        ;;
    --rollback)
        tag="${2:-}"
        [[ -n $tag ]] || die "usage: scripts/release.sh --rollback TAG"
        git fetch -q --tags origin
        [[ $(git cat-file -t "refs/tags/$tag" 2>/dev/null) == tag ]] || die "no release tag '$tag'"
        body=$(git tag -l --format='%(contents)' "$tag")
        digest=$(awk '$1 == "digest:" { print $2 }' <<<"$body")
        commit=$(awk '$1 == "commit:" { print $2 }' <<<"$body")
        [[ $digest == sha256:* && -n $commit ]] || die "tag '$tag' has no digest/commit record"
        verify_attestation "$digest" "$commit"
        deploy "$digest" "$commit" "rollback-to-$tag"
        cat <<MSG
Rolled back to $tag. If a newer release migrated the database, this older code may not run correctly
against it: restore the newest file in $DIR/backups/pre-release taken before that release
(docs/DEPLOYMENT.md, "Restore a backup").
MSG
        ;;
    '')
        gate
        tag=$(next_tag)
        deploy "$digest" "$commit" "$tag"
        if ! git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
            git tag -a "$tag" -m "Release $tag" -m "digest: $digest" -m "commit: $commit" "$commit"
            git push -q origin "refs/tags/$tag"
        fi
        say "released $tag"
        ;;
    *) die "unknown option '$1' (see --help)" ;;
esac
