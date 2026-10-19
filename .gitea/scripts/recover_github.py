"""CI-gated, fast-forward-only GitHub recovery push for one explicit commit.

Refuses unless every required gate succeeded, the checked-out commit is the
accepted SHA, and the recovery ref can only move forward. Never forces,
deletes, prunes, mirrors or pushes tags/other refs.
"""
import json
import os
import re
import subprocess
import sys

REF = "refs/heads/main"
SHA_RE = re.compile(r"[0-9a-f]{40}")


class Refused(Exception):
    pass


def git(*args, check=True, env=None):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check, env=env)


def remote_head(remote, env):
    out = git("ls-remote", remote, REF, env=env).stdout.split()
    return out[0] if out else None


def recover(sha, gates, remote, env=None):
    if not SHA_RE.fullmatch(sha or ""):
        raise Refused("full lowercase source SHA required")
    if not gates or any(result != "success" for result in gates.values()):
        raise Refused("required gates not all successful: " + json.dumps(gates, sort_keys=True))
    if git("rev-parse", "--verify", "HEAD^{commit}").stdout.strip() != sha:
        raise Refused("checked-out commit differs from accepted SHA")
    current = remote_head(remote, env)
    if current is None:
        raise Refused("recovery main is missing; not creating refs automatically")
    if current == sha:
        return "unchanged"
    git("fetch", "--no-tags", remote, REF, env=env)
    if git("merge-base", "--is-ancestor", current, sha, check=False).returncode != 0:
        raise Refused("recovery main is not an ancestor of the accepted SHA (divergent or newer)")
    git("push", "--no-tags", remote, f"{sha}:{REF}", env=env)
    if remote_head(remote, env) != sha:
        raise Refused("recovery head does not equal accepted SHA after push")
    return "pushed"


def main():
    gates = json.loads(os.environ["RECOVERY_GATES"])
    key = os.environ["RECOVERY_KEY_FILE"]
    if not os.path.isfile(key):
        raise Refused("recovery deploy key is not configured")
    hosts = os.environ["RECOVERY_KNOWN_HOSTS"]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_SSH_COMMAND=(
        f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes "
        f"-o UserKnownHostsFile={hosts}"))
    print(recover(os.environ["GITHUB_SHA"], gates, os.environ["RECOVERY_REMOTE"], env))


if __name__ == "__main__":
    try:
        main()
    except Refused as err:
        print("REFUSED: " + str(err))
        sys.exit(3)
