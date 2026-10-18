# Personal Gitea validation and HACS distribution

Prepared on 19 October 2026 Sydney. This route has not run yet; no tag, release,
public asset, live OVO request or Home Assistant installation was changed.

Source belongs to private VM300, `hallyaus/OVO_Aus_api`, with GitHub Actions
disabled on `HallyAus/OVO_Aus_api`. The public GitHub repository and existing
releases remain the HACS download compatibility catalogue. A routine recovery
push runs no GitHub build or release workflow.

## Private validation

`.gitea/workflows/ci.yml` runs only on `main` pushes or manual dispatch and uses
the dedicated `personal-ubuntu` runner. Jobs depend on one another and retain
the existing full unit, Ruff and Python 3.14 Home Assistant runtime commands.
No job uses OVO credentials, a live HA instance, a Docker socket or privileged
mode. Checkout uses only the repository job token in a temporary askpass helper;
the token is not persisted in the Git URL/config and is absent from later steps.

The official hassfest image is the job container, pinned by digest. From the
checkout working directory, run:

```sh
/usr/src/homeassistant/script/hassfest/docker/entrypoint.sh
```

That official entrypoint discovers `custom_components/*/manifest.json` relative
to the current directory, resolves absolute integration paths, changes to
`/usr/src/homeassistant`, then executes `python3 -m script.hassfest --action
validate`. Its image includes Python and the installed HA validation tree.
The checkout step checks for Git and, on the Alpine image, installs Git with
the image's configured Alpine repositories if absent. The runner supplies a
shell command rather than executing the image entrypoint at container startup;
this and private artifact upload must be verified in the first actual run.

The final job creates `ovo_energy_au.zip` from regular **tracked Git blobs** at
the exact source SHA. Entries use POSIX paths, fixed timestamps and stable
permissions/order. Symlinks, traversal, generated Python bytecode, an empty
package and overwriting an existing archive are refused. The archive is read
back and compared byte-for-byte to Git blobs. `provenance.json` records source,
tree, version, SHA256, originating run and preceding gate results. Neither file
is a shipping action. The pinned upload-artifact v3 action retains both on
private Gitea for 14 days; it does not upload to GitHub.

Pinned images were resolved from the official registries on 18 October UTC:

| Purpose | Image |
| --- | --- |
| Original Python 3.12 units | `python:3.12-bookworm@sha256:5560e9ab8709f459489e5b8aa696eda8a07ef821e14bb122be62d91234bfa98b` |
| Actual HA runtime | `python:3.14-bookworm@sha256:7ee7e4d4fb42c3ad45b8fdc473b64ec69c3cf6e80ae5d52f6fa55f77fac29027` |
| Official hassfest | `ghcr.io/home-assistant/hassfest@sha256:2dce3c5423a600e7965e5a3d5a95e0707e8452fb001ab2b5d0602099bbecba92` |
| Artifact action Node runtime | `node:24-bookworm@sha256:14078204b6bb268c107ceff6d3c43f45a888105e5c2b18b14c32b3409d93a1b0` |

Update pins through a reviewed change; do not silently use floating validators.

## HACS gate remains external and required

The official HACS action is not a validator of the local checkout. It validates
a **public GitHub** repository/ref and explicitly requires a GitHub token.
Its current source rejects private repositories. Passing the Gitea job token
would send a private-service credential to GitHub and is prohibited. Extracting
the local `gh` OAuth/PAT token or copying its auth file is also prohibited.
No documented token-free official mode was found. An empty token that happens
to bypass a `None` check is not treated as a supported authentication mode.

The prepared manual-only `.gitea/workflows/hacs-public-validation.yml` fails
closed until repository-only `HACS_PUBLIC_READ_TOKEN` is configured through a
separate reviewed handoff. It invokes the unchanged official image against
`HallyAus/OVO_Aus_api` and the exact primary workflow SHA, after checking Daniel's
identity, fixed public repository ID and matching public commit. It unsets
Gitea token fallback environment variables before invoking GitHub clients. It
never posts comments or publishes anything. Do not supply a Gitea token or
extract/copy local `gh` authentication. No credential was created or requested
while preparing this code.

Minimum proposed fine-grained GitHub access is **Contents: read** and the
automatic **Metadata: read**, resource owner `HallyAus`, only selected
`OVO_Aus_api` repository, shortest practical expiry. GitHub documents these
permissions for repository content/release reads. HACS's `issues` check reads
the repository's `has_issues` metadata; it does not need issue write access.
The fixed manual ref avoids PR discovery/comment behavior. Do not grant Actions,
Workflows, Administration, issue/PR write or contents write. Reads of other
public HACS/default/brand metadata remain ordinary public resources. Actual
least-privilege compatibility still needs the first authenticated official run;
do not broaden access automatically if it fails.

The private candidate is **not release-ready** until that official HACS run
passes for the identical public recovery SHA. No HACS check is ignored, mocked
or claimed passed here. The existing catalogue continues to work while this
gate is resolved.
Pinned official image for later reviewed integration:
`ghcr.io/hacs/action@sha256:2cbf62255159613a0e2f07decda684007f4d3d99abed5d9820a2818e02dbb98a`;
source revision `cc187cf258940a2a7acb5404773625465d7bf5a8`.

## Manual release, no hosted compute

Do not bump or ship a version just to migrate CI. The existing v4.10.0 release
and asset remain untouched. For a separately authorized future product release:

1. Complete the exact-source Gitea run and download its private candidate.
2. Push identical completed commits to GitHub recovery. Confirm Actions remains
   disabled and no recovery push builds/deploys.
3. Complete the official HACS validation gate against that exact SHA. Preserve
   its evidence; a successful hassfest check does not replace HACS validation.
4. Review version equality, release notes/referral text and every release hold.
   Only an authorized shipping operation may create a stable tag. Push the
   immutable tag to Gitea first, then the same tag to GitHub; never move it.
5. Inspect the successful Gitea run itself, not just the downloaded receipt.
   Run the **read-only** planner using normal existing local `gh` login:

   ```sh
   python .gitea/scripts/release_plan.py --candidate downloaded-candidate \
     --reviewed-run-url http://192.168.1.130:3000/hallyaus/OVO_Aus_api/actions/runs/RUN \
     --reviewed-hacs-result http://192.168.1.130:3000/hallyaus/OVO_Aus_api/actions/runs/HACS_RUN \
     --reviewed-hacs-sha EXACT_TESTED_SHA \
     --notes-file reviewed-release-notes.md
   ```

   The planner checks the personal identity/repository, disabled Actions,
   original artifact SHA256/members, exact source, existing immutable primary
   and recovery tags, every preceding Gitea gate, and absence of an existing
   release. It prints commands but has **no publication mode** and reads no
   credential values. The `reviewed-*` inputs record explicit operator
   review; they are not an automated attestation service.
6. Separately execute the reviewed draft command only when authorized. Download
   its asset, compare checksum and POSIX paths, then separately publish that
   same draft. Recheck public release/tag/asset and HACS resolution. No overwrite,
   auto-generated tag, replacement asset or additional hosted compute is used.

## Primary references

- [Official hassfest entrypoint](https://github.com/home-assistant/core/blob/dev/script/hassfest/docker/entrypoint.sh)
- [Official hassfest wrapper](https://github.com/home-assistant/actions/blob/master/hassfest/action.yml)
- [Official HACS action implementation](https://github.com/hacs/integration/blob/cc187cf258940a2a7acb5404773625465d7bf5a8/action/action.py)
- [HACS action behaviour](https://www.hacs.xyz/docs/publish/action/)
- [Gitea artifacts](https://docs.gitea.com/usage/actions/artifacts/)
- [GitHub content read permissions](https://docs.github.com/en/rest/repos/contents#get-repository-content)
- [GitHub release read permissions](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
