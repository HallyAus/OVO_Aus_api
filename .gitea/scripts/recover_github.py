"""CI-gated, fast-forward-only GitHub recovery push for one explicit commit.

Refuses unless every required gate succeeded, the checked-out commit is the
accepted SHA, and the recovery ref can only move forward. Never forces,
deletes, prunes, mirrors or pushes tags/other refs.
"""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REF = "refs/heads/main"
SHA_RE = re.compile(r"[0-9a-f]{40}")
REQUIRED_GATES = frozenset({"unit", "runtime", "hassfest", "candidate"})
EXPECTED_REMOTE = "git@github.com:HallyAus/OVO_Aus_api.git"


class Refused(Exception):
    pass


def git(*args, check=True, env=None):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check, env=env)


def remote_head(remote, env):
    out = git("ls-remote", "--", remote, REF, env=env).stdout.split()
    return out[0] if out else None


def recover(sha, gates, remote, env=None):
    if not SHA_RE.fullmatch(sha or ""):
        raise Refused("full lowercase source SHA required")
    if (not isinstance(gates, dict) or not REQUIRED_GATES.issubset(gates)
            or any(result != "success" for result in gates.values())):
        raise Refused("every required gate must be present and successful")
    if (not isinstance(remote, str) or not remote or remote.startswith("-")
            or any(ord(char) < 32 or ord(char) == 127 for char in remote)):
        raise Refused("a repository remote, not command options or control characters, is required")
    if git("rev-parse", "--verify", "HEAD^{commit}", env=env).stdout.strip() != sha:
        raise Refused("checked-out commit differs from accepted SHA")
    current = remote_head(remote, env)
    if current is None:
        raise Refused("recovery main is missing; not creating refs automatically")
    if current == sha:
        return "unchanged"
    git("fetch", "--no-tags", "--", remote, REF, env=env)
    if git("merge-base", "--is-ancestor", current, sha, check=False, env=env).returncode != 0:
        raise Refused("recovery main is not an ancestor of the accepted SHA (divergent or newer)")
    git("push", "--no-tags", "--", remote, f"{sha}:{REF}", env=env)
    if remote_head(remote, env) != sha:
        raise Refused("recovery head does not equal accepted SHA after push")
    return "pushed"


def main():
    remote = os.environ.get("RECOVERY_REMOTE")
    if remote != EXPECTED_REMOTE:
        raise Refused("only the explicit canonical GitHub repository is allowed")
    gates = json.loads(os.environ["RECOVERY_GATES"])
    key = os.environ["RECOVERY_KEY_FILE"]
    key_path = Path(key)
    if not key_path.is_file():
        raise Refused("recovery deploy key is not configured")
    if os.name == "posix" and key_path.stat().st_mode & 0o077:
        raise Refused("recovery deploy key must not be accessible to group or other users")
    hosts = os.environ["RECOVERY_KNOWN_HOSTS"]
    if not Path(hosts).is_file():
        raise Refused("reviewed SSH known-hosts file is not configured")
    # Git evaluates GIT_SSH_COMMAND through a shell. Quote every argument and
    # quote the OpenSSH option value separately so spaces in paths are literal.
    for path in (key, hosts):
        if any(ord(char) < 32 or ord(char) == 127 for char in path) or "%" in path or "${" in path:
            raise Refused("SSH file paths must not contain control characters or expansion tokens")
    ssh_args = [
        "ssh", "-F", os.devnull, "-i", key,
        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + json.dumps(hosts),
    ]
    # The deploy key already lives in a private file. Do not hand plaintext
    # credentials or interactive credential helpers to child processes.
    credential_variables = {
        "RECOVERY_DEPLOY_KEY", "SOURCE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITEA_TOKEN",
        "INPUT_GITHUB_TOKEN", "GIT_ASKPASS", "SSH_ASKPASS",
    }
    env = {name: value for name, value in os.environ.items() if name not in credential_variables}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_SSH_VARIANT="ssh", GIT_SSH_COMMAND=shlex.join(ssh_args))
    print(recover(os.environ["GITHUB_SHA"], gates, remote, env))


if __name__ == "__main__":
    try:
        main()
    except Refused as err:
        print("REFUSED: " + str(err))
        sys.exit(3)
