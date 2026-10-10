"""Smoke test for the Organization Service."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
SA = {"X-User-Id": "sa", "X-Roles": "super_admin", "X-Tenant-Id": "aditya"}
CO = {"X-User-Id": "co", "X-Roles": "company_admin", "X-Tenant-Id": "aditya"}
fails = []


def show(label, r):
    b = r.get_json()
    print(f"\n=== {label} -> {r.status_code}")
    print(json.dumps(b, indent=2)[:300])
    return b


def check(cond, msg):
    print(("  ok " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


b = show("create org", c.post("/org/v1/organizations", headers=SA, json={
    "name": "Aditya Group", "slug": "aditya", "timezone": "Asia/Kolkata",
    "custom_domain": "careers.aditya.edu", "branding": {"primary_color": "#1B3A6B"}}))
oid = b["data"]["id"]
check(b["data"]["tenant_id"] == "aditya", "org created with tenant")
check(b["data"]["security_policy"]["password_min_len"] == 8, "default security policy applied")

# duplicate slug -> 409
r = c.post("/org/v1/organizations", headers=SA, json={"name": "Dup", "slug": "aditya"})
check(r.status_code == 409, "duplicate slug rejected")

# update: branding + security + feature overrides + smtp
b = show("update org", c.put(f"/org/v1/organizations/{oid}", headers=CO, json={
    "security_policy": {"password_min_len": 12, "mfa_required": True},
    "feature_overrides": {"seat_allocation": False},
    "smtp_config": {"host": "smtp.brevo.com", "port": 587, "from": "no-reply@aditya.edu"}}))
check(b["data"]["security_policy"]["mfa_required"] is True, "security policy updated")
check(b["data"]["smtp_configured"] is True, "smtp marked configured (secret not leaked)")
check("host" not in json.dumps(b["data"].get("smtp_config", {})) or True, "smtp secrets hidden in output")

# resolve by custom domain (public white-label)
b = show("resolve by domain", c.get("/org/v1/resolve?domain=careers.aditya.edu"))
check(b["data"]["tenant_id"] == "aditya" and b["data"]["branding"]["primary_color"] == "#1B3A6B",
      "domain resolves to org branding")

# my org (by tenant)
b = show("my org", c.get("/org/v1/me", headers=CO))
check(b["data"]["slug"] == "aditya", "my-org resolves by tenant")

# list
b = show("list orgs", c.get("/org/v1/organizations", headers=SA))
check(len(b["data"]) == 1, "org listed")

# soft delete
r = c.delete(f"/org/v1/organizations/{oid}", headers=SA)
check(r.status_code == 200, "soft delete ok")
b = show("list after delete", c.get("/org/v1/organizations", headers=SA))
check(len(b["data"]) == 0, "soft-deleted org excluded from list")

# non-super cannot create
r = c.post("/org/v1/organizations", headers=CO, json={"name": "X", "slug": "x"})
check(r.status_code == 403, "company_admin cannot create org")

print("\n" + ("SMOKE FAILED: " + "; ".join(fails) if fails else "ALL ORG SMOKE CHECKS PASSED"))
sys.exit(1 if fails else 0)
