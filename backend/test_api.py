import httpx, json

base = "http://localhost:8000"

# Health check
r = httpx.get(f"{base}/health")
print("Health:", r.json())

# Summary
r = httpx.get(f"{base}/api/alerts/summary")
data = r.json()
print("\nAlert Summary:")
for dept in ["Finance","HR","Sales","Operations"]:
    d = data.get(dept, {})
    print(f"  {dept}: {d.get('total')} alerts ({d.get('critical')} critical, {d.get('open')} open)")

overall = data.get("overall", {})
print(f"\nOverall: {overall.get('total')} total, {overall.get('open')} open, {overall.get('critical')} critical")

# First 3 alerts
r = httpx.get(f"{base}/api/alerts/?limit=3")
alerts = r.json()["alerts"]
print("\nSample Alerts:")
for a in alerts:
    print(f"  [{a['severity']}] {a['department']} - {a['title'][:60]}")
