from nexus_client import publish

result = publish(
    "analytics.observation" if "nova" == "nova" else "perception.observation",
    {
        "subject": "machine-mind-nova-acceptance",
        "status": "acceptance-test",
        "confidence": 0.99,
    },
    correlation_id="machine-mind-nova-acceptance",
)
print("MACHINE_MIND_NOVA_E2E", result)
if not result.get("sent"):
    raise SystemExit(1)
