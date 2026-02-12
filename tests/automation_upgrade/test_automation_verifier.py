from tools.automation_verifier import confidence_from_evidence, evaluate_platforms, PlatformObservation


def test_confidence_bounds():
    items = [{"kind": "process", "value": "chrome.exe"}, {"kind": "dom_selector", "value": "#app"}]
    assert 80 <= confidence_from_evidence(items, "full") <= 100
    assert confidence_from_evidence(items, "none") <= 50


def test_evaluate_platforms_schema_minimal():
    platforms = [
        PlatformObservation(
            platform_key="whatsapp",
            visible_name="WhatsApp",
            platform_type="native",
            process_or_package="whatsapp.exe",
            source="window",
        )
    ]
    out = evaluate_platforms(platforms, autofix=False)
    assert "platforms" in out
    assert "summary" in out
    first = out["platforms"][0]
    for key in [
        "id",
        "visible_name",
        "type",
        "process_or_package",
        "in_platforms_adapter",
        "adapter_name",
        "automation_possible",
        "confidence",
        "evidence",
        "verification_steps",
        "required_adapter_changes",
        "next_actions",
    ]:
        assert key in first
