from pathlib import Path

vault = Path("AI_Employee_Vault")
folders = ["Inbox","Needs_Action","Done","Pending_Approval","Approved","Rejected","Plans","Briefings","Logs"]

print()
print("Vault Status After Clean")
print("=" * 45)
for f in folders:
    p = vault / f
    files = [x for x in p.glob("*") if x.is_file()] if p.exists() else []
    count = len(files)
    names = ", ".join(x.name[:40] for x in files[:2])
    tag = " <-- TEST EMAIL READY" if f == "Inbox" and count > 0 else ""
    print(f"  {f:20s} {count} file(s)  {names}{tag}")

print()
print("Config files (preserved):")
for f in ["Dashboard.md", "Company_Handbook.md", "Business_Goals.md"]:
    ok = (vault / f).exists()
    print(f"  [{'OK' if ok else 'MISSING'}] {f}")
skills = list((vault / "Skills").glob("*.md"))
print(f"  [OK] Skills/ ({len(skills)} skills preserved)")
print()
print("Vault is clean. Drop inbox file into Watcher to start test.")
