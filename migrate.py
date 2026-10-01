#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import json
import argparse
import sys

def get_all_gitea_repos(base_url, token):
    """Fetches personal repos and org repos, and returns a list of known org names."""
    repos = []
    org_names = []
    
    # 1. Fetch personal repositories
    print(f"Fetching personal repositories from {base_url}...")
    page = 1
    while True:
        url = f"{base_url.rstrip('/')}/api/v1/user/repos?limit=50&page={page}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req) as response:
                page_data = json.loads(response.read().decode('utf-8'))
                if not page_data:
                    break
                repos.extend(page_data)
                page += 1
        except urllib.error.URLError as e:
            print(f"Error fetching personal repos on page {page}: {e}")
            break
            
    # 2. Fetch list of organizations
    print("\nFetching user organizations...")
    orgs_url = f"{base_url.rstrip('/')}/api/v1/user/orgs"
    req = urllib.request.Request(orgs_url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as response:
            orgs = json.loads(response.read().decode('utf-8'))
            org_names = [org["username"] for org in orgs]
    except urllib.error.URLError as e:
        print(f"Error fetching organizations: {e}")

    # 3. Fetch repositories for each organization
    for org_name in org_names:
        print(f"Fetching repositories for organization: {org_name}...")
        page = 1
        while True:
            url = f"{base_url.rstrip('/')}/api/v1/orgs/{urllib.parse.quote(org_name)}/repos?limit=50&page={page}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {token}")
            req.add_header("Accept", "application/json")
            try:
                with urllib.request.urlopen(req) as response:
                    page_data = json.loads(response.read().decode('utf-8'))
                    if not page_data:
                        break
                    repos.extend(page_data)
                    page += 1
            except urllib.error.URLError as e:
                print(f"Error fetching org repos for {org_name} on page {page}: {e}")
                break

    # Deduplicate by full_name (e.g., 'org/repo') to prevent migrating twice
    unique_repos = {repo["full_name"]: repo for repo in repos}
    final_repos = list(unique_repos.values())
    
    print(f"\nFound {len(final_repos)} total unique repositories to migrate.")
    return final_repos, org_names

def ensure_org_exists(org_name, forgejo_url, forgejo_token):
    """Checks if an org exists on Forgejo, and creates it if it doesn't."""
    check_url = f"{forgejo_url.rstrip('/')}/api/v1/orgs/{urllib.parse.quote(org_name)}"
    req_check = urllib.request.Request(check_url)
    req_check.add_header("Authorization", f"token {forgejo_token}")
    
    try:
        urllib.request.urlopen(req_check)
        return True # Org exists
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"Failed to check org {org_name}: {e}")
            return False
            
    # If we get a 404, create the org
    print(f"Organization '{org_name}' not found on target. Creating it...")
    create_url = f"{forgejo_url.rstrip('/')}/api/v1/orgs"
    payload = {"username": org_name, "repo_admin_change_team_access": True}
    
    req_create = urllib.request.Request(create_url, data=json.dumps(payload).encode('utf-8'), method="POST")
    req_create.add_header("Authorization", f"token {forgejo_token}")
    req_create.add_header("Content-Type", "application/json")
    
    try:
        urllib.request.urlopen(req_create)
        print(f"[SUCCESS] Created missing Organization: {org_name}")
        return True
    except urllib.error.HTTPError as e:
        print(f"Failed to create org {org_name}: {e.read().decode('utf-8')}")
        return False

def migrate_repo(repo, gitea_token, forgejo_url, forgejo_token, known_orgs):
    """Triggers the built-in migration endpoint on Forgejo for a single repo."""
    endpoint = f"{forgejo_url.rstrip('/')}/api/v1/repos/migrate"
    owner_login = repo.get("owner", {}).get("login", "")
    
    # Check our known list of organizations instead of relying on the API 'type' field
    if owner_login in known_orgs:
        ensure_org_exists(owner_login, forgejo_url, forgejo_token)
    
    def attempt_migration():
        payload = {
            "clone_addr": repo["clone_url"],
            "auth_token": gitea_token,
            "repo_name": repo["name"],
            "repo_owner": owner_login,
            "description": repo.get("description", ""),
            "private": repo.get("private", True),
            "issues": True,
            "labels": True,
            "milestones": True,
            "pull_requests": True,
            "releases": True,
            "wiki": True
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(endpoint, data=data, method="POST")
        req.add_header("Authorization", f"token {forgejo_token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                print(f"[OK] Migrated: {repo.get('full_name', repo['name'])}")
                return "success"
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            if "already exists" in error_body:
                print(f"[SKIPPED] {repo.get('full_name', repo['name'])}: Already exists on target.")
                return "success"
            elif e.code == 422 and "user does not exist" in error_body:
                return "missing_namespace"
            else:
                print(f"[FAILED] {repo.get('full_name', repo['name'])}: HTTP {e.code} - {error_body}")
                return "failed"
        except urllib.error.URLError as e:
            print(f"[FAILED] {repo.get('full_name', repo['name'])}: Connection Error - {e}")
            return "failed"

    result = attempt_migration()
    
    # Fallback retry just in case a user namespace is missing and happens to be an undocumented org
    if result == "missing_namespace":
        print(f"[!] Namespace '{owner_login}' missing on target. Attempting to force-create as Organization...")
        if ensure_org_exists(owner_login, forgejo_url, forgejo_token):
            retry_result = attempt_migration()
            if retry_result == "missing_namespace":
                print(f"[FAILED] {repo.get('full_name', repo['name'])}: Server still reports missing namespace.")
                                                                                     
        else:
            print(f"[FAILED] {repo.get('full_name', repo['name'])}: Could not create Organization namespace.")

def main():
    parser = argparse.ArgumentParser(description="Zero-dependency Gitea to Forgejo API Migrator")
    parser.add_argument("--gitea-url", required=True, help="Source Gitea URL (e.g., https://git.old.com)")
    parser.add_argument("--gitea-token", required=True, help="Source Gitea Personal Access Token")
    parser.add_argument("--forgejo-url", required=True, help="Target Forgejo URL (e.g., https://git.new.com)")
    parser.add_argument("--forgejo-token", required=True, help="Target Forgejo Personal Access Token")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be migrated without making any changes")
    
    args = parser.parse_args()
    
    repos, known_orgs = get_all_gitea_repos(args.gitea_url, args.gitea_token)
    
    if not repos:
        print("No repositories found to migrate.")
        sys.exit(0)
        
    print("\nStarting migration...")
    for repo in repos:
        if args.dry_run:
            owner_login = repo.get("owner", {}).get("login", "")
            is_org = "Yes" if owner_login in known_orgs else "No"
            visibility = "Private" if repo.get("private", True) else "Public"                                                    
            print(f"[DRY RUN] Would migrate: {repo['full_name']} | Visibility: {visibility} | Source: {repo['clone_url']}")
        else:
            migrate_repo(repo, args.gitea_token, args.forgejo_url, args.forgejo_token, known_orgs)
        
    print("\nMigration run complete.")

if __name__ == "__main__":
    main()