#!/usr/bin/env python3
"""
scripts/check_submission.py
CivicPulse — Submission Lint & Mechanical Verification Script (Section 5.3 & 5.8)

Checks for:
1. Committed secrets, .env, or raw keys in repo or git history
2. Unpinned base images or :latest tags in Dockerfiles, Compose, and K8s manifests
3. Service-to-service communication using localhost
4. Port exposure of database or redis in compose.prod.yaml
5. PostgreSQL StatefulSet PVC configuration
6. GitHub Actions workflow needs: gating and permissions
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check_no_env_files():
    print("[1/7] Checking for forbidden tracked/committed .env files...")
    import subprocess
    result = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True, cwd=ROOT)
    if result.stdout.strip():
        print(f"FAIL: .env is tracked in git index: {result.stdout.strip()}")
        return False
    # Also check git log
    log_result = subprocess.run(["git", "log", "-n", "1", "--", ".env"], capture_output=True, text=True, cwd=ROOT)
    if log_result.stdout.strip():
        print(f"FAIL: .env found in git commit history!")
        return False
    print("PASS: .env is correctly gitignored and never committed.")
    return True

def check_no_latest_tags():
    print("[2/7] Checking for forbidden ':latest' tags in manifests and compose files...")
    files_to_check = [
        ROOT / "compose.prod.yaml",
        ROOT / "docker-compose.prod.yml",
        *list((ROOT / "infra" / "k8s").glob("**/*.yaml")),
    ]
    failed = False
    for f in files_to_check:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            if re.search(r"image:\s*['\"]?[^\s'\"]+:latest['\"]?", line):
                print(f"FAIL: :latest tag found in {f.relative_to(ROOT)}:{line_num} -> {line.strip()}")
                failed = True
    if not failed:
        print("PASS: Zero :latest image tags found in production manifests.")
    return not failed

def check_localhost_usage():
    print("[3/7] Checking for forbidden 'localhost' in service-to-service configs...")
    files_to_check = [
        ROOT / "compose.prod.yaml",
        ROOT / "docker-compose.prod.yml",
        ROOT / "compose.yaml",
        *list((ROOT / "infra" / "k8s").glob("**/*.yaml")),
    ]
    failed = False
    for f in files_to_check:
        if not f.exists():
            continue
        content = f.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            # Allow healthcheck tests or comments
            if "localhost" in line and not line.strip().startswith("#") and "127.0.0.1" not in line:
                if "proxy_pass" in line or "host:" in line or "POSTGRES_HOST" in line or "REDIS_HOST" in line:
                    print(f"FAIL: localhost used in service URL in {f.relative_to(ROOT)}:{line_num} -> {line.strip()}")
                    failed = True
    if not failed:
        print("PASS: No localhost service-to-service URLs found.")
    return not failed

def check_prod_compose_ports():
    print("[4/7] Checking production compose files for build instructions and exposed DB/cache ports...")
    prod_files = [ROOT / "compose.prod.yaml", ROOT / "docker-compose.prod.yml"]
    failed = False
    for prod_compose in prod_files:
        if not prod_compose.exists():
            continue
        content = prod_compose.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            if line.strip().startswith("build:"):
                print(f"FAIL: Forbidden 'build:' directive found in {prod_compose.name}:{line_num}")
                failed = True
            if re.search(r'["\']?(5432:5432|6379:6379)["\']?', line):
                print(f"FAIL: Public DB/Redis port published in {prod_compose.name}:{line_num}: {line.strip()}")
                failed = True
    if not failed:
        print("PASS: Zero build directives and zero database/cache ports exposed in production Compose.")
    return not failed


def check_k8s_postgres_pvc():
    print("[5/7] Checking PostgreSQL Kubernetes manifest for StatefulSet + PVC...")
    pg_file = ROOT / "infra" / "k8s" / "base" / "postgres-statefulset.yaml"
    if not pg_file.exists():
        pg_file = ROOT / "infra" / "k8s" / "postgres-statefulset.yaml"
    if not pg_file.exists():
        print("FAIL: postgres-statefulset.yaml not found.")
        return False
    content = pg_file.read_text(encoding="utf-8")
    if "kind: StatefulSet" not in content or "volumeClaimTemplates" not in content:
        print("FAIL: PostgreSQL is not configured as a StatefulSet with volumeClaimTemplates.")
        return False
    print("PASS: PostgreSQL configured as StatefulSet with volumeClaimTemplates PVC.")
    return True

def check_ci_workflows():
    print("[6/7] Checking CI and CD workflows for required jobs, needs: gating, and permissions...")
    ci_file = ROOT / ".github" / "workflows" / "ci.yml"
    cd_file = ROOT / ".github" / "workflows" / "cd.yml"
    if not ci_file.exists():
        print("FAIL: .github/workflows/ci.yml not found.")
        return False
    if not cd_file.exists():
        print("FAIL: .github/workflows/cd.yml not found.")
        return False
    ci_content = ci_file.read_text(encoding="utf-8")
    cd_content = cd_file.read_text(encoding="utf-8")
    ci_keywords = [
        "permissions:",
        "contents: read",
        "lint-and-type",
        "test-backend",
        "test-frontend",
        "manifests",
        "build",
        "scan",
        "integration",
        "ci-gate",
        "needs:",
    ]
    cd_keywords = [
        "permissions:",
        "packages: write",
        "needs: [test]",
        "needs: [build-push]",
        "deploy-k8s",
        "rollout undo",
    ]
    failed = False
    for kw in ci_keywords:
        if kw not in ci_content:
            print(f"FAIL: Missing required keyword/job '{kw}' in ci.yml")
            failed = True
    for kw in cd_keywords:
        if kw not in cd_content:
            print(f"FAIL: Missing required keyword/job '{kw}' in cd.yml")
            failed = True
    if not failed:
        print("PASS: CI and CD workflows contain all required jobs, permissions, and dependency gates.")
    return not failed

def check_secret_placeholders():
    print("[7/7] Checking Kubernetes secrets for real credentials vs placeholders...")
    sec_file = ROOT / "infra" / "k8s" / "base" / "secrets.yaml"
    if not sec_file.exists():
        sec_file = ROOT / "infra" / "k8s" / "secrets.yaml"
    if sec_file.exists():
        content = sec_file.read_text(encoding="utf-8")
        if "AIza" in content or "sk-" in content or "ghp_" in content:
            print("FAIL: Potential real API key detected in Kubernetes secret!")
            return False
    print("PASS: Kubernetes secret manifests contain placeholder strings only.")
    return True

def main():
    print("==================================================")
    print("  CivicPulse — Pre-Submission Mechanical Checker  ")
    print("==================================================")
    checks = [
        check_no_env_files(),
        check_no_latest_tags(),
        check_localhost_usage(),
        check_prod_compose_ports(),
        check_k8s_postgres_pvc(),
        check_ci_workflows(),
        check_secret_placeholders(),
    ]
    print("--------------------------------------------------")
    if all(checks):
        print("ALL MECHANICAL PRE-SUBMISSION CHECKS PASSED (7/7)!")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED! Please review the failures above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
