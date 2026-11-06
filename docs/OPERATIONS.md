# Operations

Everything runs from the workstation, in `main`. Defaults: `MEAL_PREP_NAS=nas-user@<wifi-ip>`, `MEAL_PREP_NAS_DIR=/volume1/docker/meal-prep`. Override them if the NAS moves.

## Release

```bash
git switch main && git pull
scripts/release.sh --dry-run   # gate only
scripts/release.sh             # gate, backup, deploy, health check, tag
```

The gate requires a clean `main` equal to `origin/main`, green CI for that commit, its image in GHCR and a valid attestation. On a failed deploy the script returns to the previous release and creates no tag.

## Rollback

```bash
git tag -l 'v*' --sort=-creatordate | head
scripts/release.sh --rollback vYYYY.MM.DD
```

If the newer release migrated the database, restore the backup taken just before it as well.

## Backups

On the NAS, in `/volume1/docker/meal-prep/backups/`, integrity-checked when written:

| Folder | When | Kept |
|---|---|---|
| `weekly/` | Once per ISO week, by the `meal-prep-backup` container | 12 |
| `pre-release/` | Before every deploy | 20 |

A week's work can be lost at worst if the database itself is damaged. For a safe copy before something risky:

```bash
ssh $NAS 'docker exec meal-prep-backup backup-now.sh /backups/pre-release/mealplanner-manual-$(date +%Y%m%d%H%M).db'
```

These copies sit on the same disk as the database, so they protect against mistakes and corruption, not disk failure.

**Off-disk copy:** to be added when the second disk arrives.

## Restore a backup

```bash
cd /volume1/docker/meal-prep
docker ps                      # note what is running
docker stop meal-prep meal-prep-backup
docker run --rm --user 10001:10001 -v "$PWD/data:/data" -v "$PWD/backups:/backups" \
  --entrypoint python "ghcr.io/jflopezo91/meal-prep@$(sed -n 's/^MEAL_PREP_DIGEST=//p' .env)" \
  -m mealplanner.entrypoints.db_cli restore --src /backups/weekly/<file>.db --db /data/mealplanner.db --force
docker start meal-prep meal-prep-backup
```

## First-time NAS setup

```bash
D=/volume1/docker/meal-prep
mkdir -p $D/data $D/secrets $D/backups/weekly $D/backups/pre-release
setfacl -b -R $D          # folders under /volume1/docker inherit an open ACL; chmod alone is not enough
ssh-keygen -q -t ed25519 -N "" -C meal-prep-nas -f $D/secrets/deploy_key
chmod 700 $D/secrets; chmod 600 $D/secrets/deploy_key
docker run --rm -v $D:/m alpine sh -c 'chown -R 10001:10001 /m/data /m/secrets /m/backups && chmod 700 /m/data'
```

Add `deploy_key.pub` to `jflopezo91/meal-plan` as a write deploy key. The private key never leaves the NAS. SSH must stay enabled in the NAS for releases.

## Move to another PC

Install Docker and `gh`, clone the repo, run `gh auth login`, and add the new PC's SSH public key to `~/.ssh/authorized_keys` on the NAS.

## Performance

To be measured (migration plan, step 6). The limits in `deploy/docker-compose.yml` are provisional.
