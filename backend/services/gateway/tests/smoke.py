"""Integration smoke: Gateway (test client) -> live Auth Service on :8001."""
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from app.factory import build_app

app = build_app()
c = app.test_client()
fails = []


def show(label, resp):
    try:
        body = resp.get_json()
    except Exception:
        body = {"_raw": resp.get_data(as_text=True)[:200]}
    print(f"\n=== {label} -> {resp.status_code}")
    print(json.dumps(body, indent=2)[:400])
    return body


# health
r = c.get("/health"); assert r.status_code == 200

# public: login through gateway
r = c.post("/auth/v1/login", json={"email": "admin@lareitcloudsolutions.com", "password": "ChangeMe#123"})
body = show("login via gateway (public)", r)
if r.status_code != 200: fails.append("login")
access = body["data"]["access_token"]

# protected: /me with bearer -> gateway verifies + injects headers -> auth
r = c.get("/auth/v1/me", headers={"Authorization": f"Bearer {access}"})
body = show("me via gateway (verified+injected)", r)
if r.status_code != 200 or body["data"]["email"] != "admin@lareitcloudsolutions.com":
    fails.append("me")
if "super_admin" not in body["data"]["roles"]:
    fails.append("roles-injected")

# protected without token -> 401 at gateway
r = c.get("/auth/v1/me")
show("me no-token (expect 401 at gateway)", r)
if r.status_code != 401: fails.append("noauth")

# spoofed trusted header, no bearer -> gateway strips + requires token -> 401
r = c.get("/auth/v1/me", headers={"X-User-Id": "spoofed", "X-Roles": "super_admin"})
show("me spoofed X-User-Id, no token (expect 401)", r)
if r.status_code != 401: fails.append("spoof-blocked")

# spoofed header WITH a valid student-less token: gateway must override X-Roles
# with the real (empty) roles, so admin-only would 403 downstream. Here we just
# confirm /me returns the real identity, not the spoofed one.
r = c.get("/auth/v1/me", headers={"Authorization": f"Bearer {access}", "X-User-Id": "spoofed"})
body = show("me spoofed + valid token (expect real identity)", r)
if r.status_code != 200 or body["data"]["email"] != "admin@lareitcloudsolutions.com":
    fails.append("spoof-override")

# unknown route -> 404 route_not_found
r = c.get("/nope/v1/thing", headers={"Authorization": f"Bearer {access}"})
body = show("unknown route (expect 404 route_not_found)", r)
if r.status_code != 404 or body["errors"][0]["code"] != "route_not_found":
    fails.append("unknown-route")

# register a new user through the gateway (public)
r = c.post("/auth/v1/register", json={"email": "gw-test@aditya.edu", "password": "Passw0rd!", "full_name": "GW Test"})
show("register via gateway (public)", r)
if r.status_code not in (201, 409): fails.append("register")

print("\n" + "=" * 40)
if fails:
    print("FAILURES:", fails); sys.exit(1)
print("ALL GATEWAY SMOKE CHECKS PASSED")
