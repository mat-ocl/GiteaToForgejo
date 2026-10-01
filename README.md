# Gitea to Forgejo Migrator

Python script to batch-migrate repositories, organizations, issues, PRs, wikis, and milestones from a source Gitea instance to a target Forgejo instance via REST APIs.

## Features

- **Zero Third-Party Dependencies:** Runs entirely on standard Python 3 (`urllib`, `json`, `argparse`).
- **Complete Metadata Transfer:** Migrates repository code, wikis, issues, pull requests, labels, milestones, and releases using Forgejo's native migration engine.
- **Organization Auto-Provisioning:** Detects source organizations and automatically creates missing organizations on the target instance before initiating repository imports.
- **Deduplication & Collision Safety:** Skips repositories that already exist on the target instance.
- **Dry-Run Mode:** Inspect all target repositories, permissions, and clone URLs before triggering migrations.

---

## Prerequisites

- **Python 3.8+** installed locally.
- **Gitea Personal Access Token** (Source) with permissions:
  - `read:repository`
  - `read:organization`
  - `read:user`
- **Forgejo Personal Access Token** (Target) with permissions:
  - `write:repository`
  - `write:organization`
  - `write:user`

---

## Installation

Clone the repository and mark the script as executable:

```bash
git clone [https://github.com/mat-ocl/GiteaToForgejo.git](https://github.com/mat-ocl/GiteaToForgejo.git)
cd GiteaToForgejo
chmod +x migrate.py

```

---

## Usage

### Test with a Dry Run

Always run a dry run first to verify token access and view the discovery list:

```bash
python3 migrate.py \
  --gitea-url "[https://gitea.example.com](https://gitea.example.com)" \
  --gitea-token "your_gitea_token" \
  --forgejo-url "[https://forgejo.example.com](https://forgejo.example.com)" \
  --forgejo-token "your_forgejo_token" \
  --dry-run

```

### Execute the Migration

```bash
python3 migrate.py \
  --gitea-url "[https://gitea.example.com](https://gitea.example.com)" \
  --gitea-token "your_gitea_token" \
  --forgejo-url "[https://forgejo.example.com](https://forgejo.example.com)" \
  --forgejo-token "your_forgejo_token"

```


---

## CLI Options

| Option | Required | Description |
| --- | --- | --- |
| `--gitea-url` | Yes | Base URL of the source Gitea server (e.g., `https://gitea.example.com`) |
| `--gitea-token` | Yes | Personal access token for the source instance |
| `--forgejo-url` | Yes | Base URL of the target Forgejo server (e.g., `https://forgejo.example.com`) |
| `--forgejo-token` | Yes | Personal access token for the target instance |
| `--dry-run` | No | Lists repositories that would be migrated without performing actions |

---

## How It Works

1. **Discovery:** Fetches all personal repositories associated with the source token, lists all user organizations, and queries every organization's repository list.
2. **Deduplication:** Normalizes all entries by `full_name` (`owner/repo`) to avoid duplicate migration tasks.
3. **Namespace Provisioning:** For each repository owned by an organization, it checks if the organization exists on Forgejo. If not, it creates the organization automatically.
4. **Asynchronous Import:** Calls Forgejo's `/api/v1/repos/migrate` endpoint with source credentials. Forgejo queues and processes the Git clone and metadata import in the background.

---

## Troubleshooting

* **HTTP 422 Unprocessable Entity (`user does not exist`):**
Ensure your target user account on Forgejo has identical username casing/spelling as the source Gitea account.
* **HTTP 409 Conflict (`repo already exists`):**
The script safely skips repositories that already exist on the target Forgejo instance without halting the run.
* **Large Repositories Timing Out:**
Forgejo performs the migration asynchronously on its internal task queue. If a repository has extensive Git LFS assets or large history, monitor its status in Forgejo's web UI under repository settings.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

