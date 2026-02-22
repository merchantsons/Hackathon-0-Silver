"""Quick Gmail integration test — run once to verify setup."""
import os, json, sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
creds_path = Path(os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json"))
token_path  = Path(os.environ.get("GMAIL_TOKEN_PATH",      "gmail_token.json"))

print()
print("=" * 55)
print("  Gmail Integration Test — Silver Tier")
print("=" * 55)

# ── Test 1: Credentials file ──────────────────────────────
print()
print("Test 1: Credentials File")
if not creds_path.exists():
    print(f"  [FAIL] File not found: {creds_path}")
    sys.exit(1)
data = json.loads(creds_path.read_text())
info = data.get("installed", {})
print(f"  [PASS] File found   : {creds_path.name}")
print(f"  [PASS] Client ID    : {info['client_id'][:50]}...")
print(f"  [PASS] Project      : {info['project_id']}")
print(f"  [PASS] Auth URI     : {info['auth_uri']}")

# ── Test 2: Library imports ───────────────────────────────
print()
print("Test 2: OAuth2 Library Imports")
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    print("  [PASS] All OAuth2 libraries available")
except ImportError as e:
    print(f"  [FAIL] {e}")
    print("         Run: pip install google-api-python-client google-auth-oauthlib")
    sys.exit(1)

# ── Test 3: Token / Auth status ───────────────────────────
print()
print("Test 3: OAuth Token Status")
if token_path.exists():
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        print(f"  [PASS] Token file exists : {token_path.name}")
        if creds.valid:
            print("  [PASS] Token is VALID — no re-auth needed")
        elif creds.expired and creds.refresh_token:
            print("  [INFO] Token expired — will auto-refresh on next run")
            creds.refresh(Request())
            print("  [PASS] Token refreshed successfully")
            token_path.write_text(creds.to_json(), encoding="utf-8")
        else:
            print("  [WARN] Token invalid, re-auth required")
    except Exception as e:
        print(f"  [WARN] Token error: {e}")
        print("         Re-auth will happen on next non-DEV_MODE run")
else:
    print(f"  [INFO] No token yet (first-time setup)")
    print()
    print("  --> Starting browser OAuth login...")
    print("      A Google login page will open in your browser.")
    print("      Sign in and grant Gmail read permission.")
    print()
    try:
        flow  = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"  [PASS] Authorized! Token saved: {token_path.name}")
    except Exception as e:
        msg = str(e)
        print(f"  [FAIL] OAuth login failed: {msg}")
        if "access_denied" in msg or "not completed" in msg.lower():
            print()
            print("  FIX: Your Google account is not added as a Test User.")
            print("  Steps:")
            print("    1. Go to https://console.cloud.google.com")
            print("    2. Select project 'hackathon-0-silver'")
            print("    3. APIs & Services → OAuth consent screen")
            print("    4. Scroll to 'Test users' → click '+ ADD USERS'")
            print("    5. Enter your Gmail address → Save")
            print("    6. Re-run this script")
        sys.exit(1)

# ── Test 4: Live Gmail API call ───────────────────────────
print()
print("Test 4: Live Gmail API Call")
try:
    if not creds.valid:
        creds.refresh(Request())
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email_addr  = profile.get("emailAddress", "?")
    total_msgs  = profile.get("messagesTotal", 0)
    total_thds  = profile.get("threadsTotal",  0)
    print(f"  [PASS] Connected as : {email_addr}")
    print(f"  [PASS] Messages     : {total_msgs:,}")
    print(f"  [PASS] Threads      : {total_thds:,}")

    # Fetch a few unread important emails
    result = service.users().messages().list(
        userId="me", q="is:unread is:important", maxResults=5
    ).execute()
    msgs = result.get("messages", [])
    print(f"  [PASS] Unread+important: {len(msgs)} found")
    if msgs:
        print("         (first message IDs):")
        for m in msgs[:3]:
            print(f"           {m['id']}")
except Exception as e:
    print(f"  [FAIL] Gmail API call failed: {e}")
    sys.exit(1)

print()
print("=" * 55)
print("  ALL TESTS PASSED")
print("  Gmail integration is WORKING")
print("=" * 55)
print()
print("Next: run  run_gmail_watcher.bat  for live monitoring")
print()
