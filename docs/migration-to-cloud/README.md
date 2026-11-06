# Migration plan: go-live on the NAS

How it works: [ARCHITECTURE.md](../ARCHITECTURE.md). How to run things: [DEVELOPMENT.md](../DEVELOPMENT.md). Past phases and the reasoning behind them: [HISTORY.md](HISTORY.md).

## Where we are

The app is feature-complete. **What's left is 6d:** run it on the NAS and make releases a deliberate, verifiable step from the workstation. Komodo was dropped on 2026-11-05: one app does not need an orchestrator, so `scripts/release.sh` deploys over SSH.

## Target

```
 workstation                       GitHub                         NAS
 git push main ─────────────▶ CI: tests → image → GHCR digest + attestation
 scripts/release.sh            trust gate: CI green · digest for this commit · attestation verified
                               ── SSH ──▶ backup ▶ deploy by digest ▶ health + revision check
                               then an annotated tag vYYYY.MM.DD[.N] records the release
```

- **Release** = an annotated tag holding the digest. Nothing is committed to `main`, and `release.sh` never builds.
- **Rollback** = `release.sh --rollback <tag>`. A database backup is taken before every deploy.
- **LAN access:** plain HTTP on `http://<nas>:8080`, like other services. Viewing is open; changes need a login.
- **Portable:** moving to another PC takes the repo, `gh` and an SSH key the NAS accepts.
- **Not doing:** deploy-on-push, auto-update, a GitHub runner on the NAS, inbound ports or tunnels.

## Steps

Each step ends in a check, and a step that fails stops the go-live. Procedures are in [OPERATIONS.md](../OPERATIONS.md).

1. **Addresses.** Reserve the NAS address in the router. DHCP can move it. **Done when:** the NAS keeps `<wifi-ip>` after a restart.
2. **Merge to `main`** and use a `gh` with `gh attestation`. **Done when:** CI is green on `main` and the attestation verifies for that commit's image.
3. **`scripts/release.sh`.** **Done when:** a dry run prints the digest, and it refuses a dirty tree, an unpushed commit, a red CI run and a digest that fails verification.
4. **NAS folders, permissions and publish key.** **Done when:** the container reads the key as uid 10001, and both deploy keys are listed on `meal-plan`.
5. **First release and data move.** Stop the WSL container, back up, restore on the NAS, release, publish one month from a phone, then delete the WSL deploy key. **Done when:** the release commit is running, the shopping list in progress matches, Publish reaches `live`, and a publish from WSL fails.
6. **Limits.** Time a month fill on the NAS under load, and adjust the limits in `deploy/docker-compose.yml`. **Done when:** a month fill finishes within the timeout and the numbers are in OPERATIONS.md.
7. **Backups.** **Done when:** a restore of the latest weekly backup into a throwaway container shows the same plans and lists. Add the off-disk copy when the second disk arrives.
8. **Rollback drill and exposure check.** Release a trivial change and roll it back. Confirm no port forward or tunnel. **Done when:** both paths end healthy with data intact, and a phone off the Wi-Fi sees the public site but not the NAS.

## After go-live (optional)

- HTTPS on the LAN with Caddy and a DNS-challenge certificate, then `MEALPLANNER_TRUSTED_PROXIES=1` and secure cookies. No app change is needed.
- Delete the retired Pages site of `meal-prep`: `gh api -X DELETE repos/jflopezo91/meal-prep/pages`.
- Product polish:
  - Dinner-carb choice for linked meals.
  - The `bistec_a_caballo` data fix.
  - Tidy the redundant "Edit weeks" rows.
  - A regression test for creating a list across months.
- Review the reported npm audit findings.

## Decisions in force

| Topic | Decision |
|---|---|
| Hosting | Flask + SQLite in one app container on the NAS, plus a backup container. LAN only, with no inbound route or tunnel. |
| Access | Viewing is open on the LAN; changes and publishing need a household login. |
| Public site | `jflopezo91/meal-plan` holds data only; its workflow builds the frontend at the pinned `app-ref`. Everything published is public. |
| Secrets | One: the publish deploy key, a file on the NAS that can write to `meal-plan` only. |
| Images | Built and attested by GitHub, and deployed by digest only. |
| Releases | An annotated tag on `main`, gated and deployed by `release.sh` over SSH. Rollback = the previous release. |
| Planning | Independent weekly plans with no cross-week rules. Rules are advisory for swaps. |
| Shopping lists | Cells for each week and group (long-lasting/fresh), either to buy or bought. There is no pantry or purchase tracking. |
