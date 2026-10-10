"""Smoke test for the Auth Service via Flask test client."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()


def show(label, resp):
    body = resp.get_json()
    print(f"\n=== {label} -> {resp.status_code}")
    print(json.dumps(body, indent=2)[:600])
    return body


fails = []

# health
r = c.get("/health"); assert r.status_code == 200, "health failed"

# register
r = c.post("/auth/v1/register", json={"email": "stud1@aditya.edu", "password": "Passw0rd!", "full_name": "Test Student"})
show("register", r)
if r.status_code != 201: fails.append("register")

# duplicate register -> 409
r = c.post("/auth/v1/register", json={"email": "stud1@aditya.edu", "password": "Passw0rd!"})
show("register duplicate (expect 409)", r)
if r.status_code != 409: fails.append("dup-register")

# bad validation -> 400
r = c.post("/auth/v1/register", json={"email": "nope", "password": "x"})
show("register invalid (expect 400)", r)
if r.status_code != 400: fails.append("validation")

# login
r = c.post("/auth/v1/login", json={"email": "stud1@aditya.edu", "password": "Passw0rd!", "device": "pytest"})
body = show("login", r)
if r.status_code != 200: fails.append("login")
access = body["data"]["access_token"]
refresh = body["data"]["refresh_token"]

# wrong password -> 401
r = c.post("/auth/v1/login", json={"email": "stud1@aditya.edu", "password": "wrong"})
show("login wrong pw (expect 401)", r)
if r.status_code != 401: fails.append("login-wrong")

# /me with bearer
r = c.get("/auth/v1/me", headers={"Authorization": f"Bearer {access}"})
body = show("me", r)
if r.status_code != 200 or body["data"]["email"] != "stud1@aditya.edu": fails.append("me")

# /me without token -> 401
r = c.get("/auth/v1/me")
show("me no-token (expect 401)", r)
if r.status_code != 401: fails.append("me-noauth")

# refresh -> new tokens
r = c.post("/auth/v1/refresh", json={"refresh_token": refresh})
body = show("refresh", r)
if r.status_code != 200: fails.append("refresh")
new_refresh = body["data"]["refresh_token"]

# reuse old refresh -> 401 refresh_reuse
r = c.post("/auth/v1/refresh", json={"refresh_token": refresh})
body = show("refresh reuse (expect 401 refresh_reuse)", r)
if r.status_code != 401 or body["errors"][0]["code"] != "refresh_reuse": fails.append("refresh-reuse")

# after reuse, the rotated new_refresh should now be revoked too (family revoked)
r = c.post("/auth/v1/refresh", json={"refresh_token": new_refresh})
show("refresh after family revoke (expect 401)", r)
if r.status_code != 401: fails.append("family-revoke")

# admin login + list users (RBAC)
r = c.post("/auth/v1/login", json={"email": "admin@lareitcloudsolutions.com", "password": "ChangeMe#123"})
admin_access = r.get_json()["data"]["access_token"]
r = c.get("/auth/v1/users", headers={"Authorization": f"Bearer {admin_access}"})
body = show("admin list users (RBAC ok)", r)
if r.status_code != 200: fails.append("rbac-admin")

# student trying admin endpoint -> 403
r = c.get("/auth/v1/users", headers={"Authorization": f"Bearer {access}"})
show("student list users (expect 403)", r)
if r.status_code != 403: fails.append("rbac-forbidden")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("ALL SMOKE CHECKS PASSED")
