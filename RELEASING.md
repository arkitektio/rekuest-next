# Releasing rekuest-next

`rekuest-next` ships as a PyPI package (`rekuest-next`). Versioning is automated
by [python-semantic-release][psr] from [Conventional Commits][cc] — you never
bump the version by hand. A push to a release branch runs
`.github/workflows/release.yaml`, which:

1. runs the test suite,
2. computes the next version from the commit history, bumps `pyproject.toml`,
   updates `CHANGELOG.md`, tags `vX.Y.Z`, and cuts a GitHub Release,
3. builds the wheel and, **only if a release was cut**, uploads it to PyPI via
   trusted publishing (OIDC).

## Commit messages drive the version

| Commit prefix | Bump | Example |
| --- | --- | --- |
| `fix:` | patch | `fix: handle empty assignation` |
| `feat:` | minor | `feat: add actor hook` |
| `feat!:` / `BREAKING CHANGE:` footer | **major** | `feat!: new api` |

Commits that aren't releasable (`chore:`, `docs:`, `refactor:` …) don't trigger
a release on their own.

## Branches

| Branch | Releases | PyPI |
| --- | --- | --- |
| `main` | stable `X.Y.Z` | the default install (`pip install rekuest-next`) |
| `next` | prereleases `X.Y.Z-rc.N` | published as a **prerelease** — only reached via `pip install rekuest-next --pre` or an exact pin |
| `N.x` (e.g. `1.x`) | maintenance `X.Y.Z` | published stable for an older major |

PyPI marks `…-rc.N` versions as prereleases, so a plain
`pip install rekuest-next` never picks them up — `next` is a safe soak channel.

## Tag-based integration backend

`integration.yaml` runs on `main` and `next` and sets `REKUEST_SERVICE_TAG`
(`latest` on `main`, `next` elsewhere). `tests/integration/docker-compose.yml`
resolves the rekuest backend image via
`jhnnsrs/rekuest:${REKUEST_SERVICE_TAG:-next}`, so the prerelease line is tested
against the prerelease backend and the stable line against `:latest`.

## Day-to-day

- **Patch/feature for the current line:** merge a `fix:`/`feat:` PR into `main`.
  PSR cuts the next stable release and publishes it to PyPI.
- **Anything risky / breaking:** land it on `next` first. Each push cuts a fresh
  `…-rc.N` and publishes it as a PyPI prerelease so you can soak it. Promote by
  merging `next` → `main`.

## Working on a new major (v2)

```
next   feat!: …      -> 2.0.0-rc.1, 2.0.0-rc.2 …   (PyPI prereleases)
              │ merge main into next regularly to keep the rc base correct
main   ──1.6.3──(merge next)──> 2.0.0 -> 2.0.1 …    (stable PyPI)
          │ cut `1.x` from main HEAD *before* the 2.0.0 merge
1.x    ──1.6.3──> 1.6.4 -> 1.6.5 …                  (stable PyPI for v1)
```

1. **Develop v2 on `next`.** Land `feat!:` / `BREAKING CHANGE:` commits there.
   PSR cuts `2.0.0-rc.N` as PyPI prereleases. Periodically merge `main` → `next`
   so the rc base stays at the latest v1.
2. **Cut the maintenance branch first.** Right before promoting, branch `1.x`
   from `main` HEAD (still at the last v1 commit):
   ```sh
   git checkout main && git pull
   git checkout -b 1.x && git push -u origin 1.x
   ```
3. **Promote v2.** Merge `next` → `main`. The breaking change makes PSR cut
   stable `2.0.0`.

## Backporting a fix to v1 (after v2 has shipped)

Branch off `1.x`, PR the fix into `1.x` with a `fix:` commit. PSR cuts the next
patch and publishes it to PyPI. Forward-port the same fix to `main`/`next` if it
also applies there.

## Consuming the next channel

```sh
pip install rekuest-next --pre          # latest rc (or stable, whichever is newer)
pip install 'rekuest-next==2.0.0-rc.1'  # pin a specific rc
```

Stable consumers (`pip install rekuest-next`) are unaffected by the `next`
channel.

## Dry-running locally

`python-semantic-release` is in the dev group, so you can preview the version a
branch would cut without pushing anything:

```sh
uv run semantic-release version --print   # prints the next version, makes no changes
```

[psr]: https://python-semantic-release.readthedocs.io/
[cc]: https://www.conventionalcommits.org/
