import json
from datetime import date

baseline = json.loads(open(".github/dependency-audit-baseline.json").read())
if date.today().isoformat() > baseline["expires"]:
    raise SystemExit(f"Python audit baseline expired on {baseline['expires']}")

report = json.loads(open("/tmp/pip-audit.json").read())
findings = report if isinstance(report, list) else report.get("dependencies", [])
unknown = [item["name"] for item in findings if item.get("vulns") and item["name"] not in baseline["knownPackages"]]
if unknown:
    print("New Python vulnerabilities detected:", ", ".join(sorted(set(unknown))))
    raise SystemExit(1)
print("pip-audit regression gate passed; existing findings are documented with an expiry.")
