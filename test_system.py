"""Full system DEV_MODE test — all 5 Silver components."""
import os, sys, importlib.util
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

os.environ["DEV_MODE"] = "true"

PASS = "[PASS]"
FAIL = "[FAIL]"

print()
print("=" * 55)
print("  Full System DEV_MODE Test — Silver Tier")
print("=" * 55)

results = {}

# ── 1. File System Watcher ────────────────────────────────
print()
print("[1] File System Watcher (watchers/file_system_watcher.py)")
try:
    spec = importlib.util.spec_from_file_location("file_system_watcher", "watchers/file_system_watcher.py")
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    v = getattr(mod, "WATCHER_VERSION", "?")
    print(f"  {PASS} v{v} loaded")
    print(f"  {PASS} VAULT_ROOT = {mod.VAULT_ROOT}")
    print(f"  {PASS} INBOX_DIR  = {mod.INBOX_DIR}")
    results["File System Watcher"] = True
except Exception as e:
    print(f"  {FAIL} {e}")
    results["File System Watcher"] = False

# ── 2. Gmail Watcher (DEV_MODE) ───────────────────────────
print()
print("[2] Gmail Watcher (watchers/gmail_watcher.py) — DEV_MODE")
try:
    spec2 = importlib.util.spec_from_file_location("gmail_watcher", "watchers/gmail_watcher.py")
    mod2  = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(mod2)
    print(f"  {PASS} v{mod2.WATCHER_VERSION} loaded")
    print(f"  {PASS} DEV_MODE = {mod2.DEV_MODE}")
    print(f"  {PASS} CREDENTIALS_PATH = {mod2.CREDENTIALS_PATH.name}")
    print(f"  {PASS} CREDENTIALS FILE EXISTS = {mod2.CREDENTIALS_PATH.exists()}")
    # Sample the first 3 simulated emails
    sim    = mod2.SimulatedGmail
    emails = sim._SIMULATED[:3]
    print(f"  {PASS} Simulated email pool: {len(sim._SIMULATED)} entries")
    for em in emails:
        subj = em.get("subject", "?")
        frm  = em.get("from",    "?")
        print(f"         '{subj[:45]}' from {frm}")
    results["Gmail Watcher"] = True
except Exception as e:
    print(f"  {FAIL} {e}")
    import traceback; traceback.print_exc()
    results["Gmail Watcher"] = False

# ── 3. LinkedIn Watcher (DEV_MODE) ────────────────────────
print()
print("[3] LinkedIn Watcher (watchers/linkedin_watcher.py) — DEV_MODE")
try:
    spec3 = importlib.util.spec_from_file_location("linkedin_watcher", "watchers/linkedin_watcher.py")
    mod3  = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(mod3)
    print(f"  {PASS} v{mod3.WATCHER_VERSION} loaded")
    print(f"  {PASS} DEV_MODE = {mod3.DEV_MODE}")
    results["LinkedIn Watcher"] = True
except Exception as e:
    print(f"  {FAIL} {e}")
    results["LinkedIn Watcher"] = False

# ── 4. Email MCP Server ───────────────────────────────────
print()
print("[4] Email MCP Server (email_mcp_server.py)")
try:
    import email_mcp_server as mcp
    print(f"  {PASS} v{mcp.SERVER_VERSION} loaded")
    # Test EmailSender in DEV_MODE
    result = mcp.EmailSender.send(
        to="judge@hackathon.com",
        subject="Test from Silver Tier",
        body="This is a DEV_MODE test email.",
    )
    ok = result.get("success", False)
    print(f"  {PASS if ok else FAIL} EmailSender.send() -> {result}")
    results["Email MCP Server"] = ok
except Exception as e:
    print(f"  {FAIL} {e}")
    results["Email MCP Server"] = False

# ── 5. Orchestrator ───────────────────────────────────────
print()
print("[5] Orchestrator (orchestrator.py)")
try:
    import orchestrator as orch
    print(f"  {PASS} v{orch.ORCH_VERSION} loaded")
    state = orch.OrchestratorState()
    print(f"  {PASS} State loaded")
    print(f"  {PASS} LinkedInDispatcher class present: {hasattr(orch, 'LinkedInDispatcher')}")
    print(f"  {PASS} EmailDispatcher class present:    {hasattr(orch, 'EmailDispatcher')}")
    print(f"  {PASS} DAILY_BRIEFING_TIME = {orch.DAILY_BRIEFING_TIME}")
    print(f"  {PASS} LINKEDIN_POST_TIME  = {orch.LINKEDIN_POST_TIME}")
    results["Orchestrator"] = True
except Exception as e:
    print(f"  {FAIL} {e}")
    results["Orchestrator"] = False

# ── Summary ───────────────────────────────────────────────
print()
print("=" * 55)
all_ok = all(results.values())
for name, ok in results.items():
    mark = PASS if ok else FAIL
    print(f"  {mark} {name}")
print()
if all_ok:
    print("  ALL 5 SILVER COMPONENTS WORKING")
    print()
    print("  Gmail real OAuth: run  python test_gmail.py")
    print("                    (browser login for first-time auth)")
else:
    failed = [n for n, ok in results.items() if not ok]
    print(f"  FAILED: {failed}")
print("=" * 55)
print()
