from ragtrust.agents.generator import GenerationAgent


class _FakeFoundryClient:
    def run_agent_chat(self, *_args, **_kwargs):
        return """[{"question":"q","candidate_reference_answer":"a","expected_behavior":"answer","topic":"t","scenario_type":"direct","difficulty":"easy","modality":"text","seed_ids":[],"source_version_ids":[],"evidence_refs":["segment-1"],"required_facts":[],"reference_origin":"automatically_derived"}]"""


def test_foundry_generation_normalizes_segment_ids_to_locators(monkeypatch):
    monkeypatch.setattr(
        "ragtrust.agents.generator.FoundryAgentClient.get_instance",
        lambda: _FakeFoundryClient(),
    )
    generated = GenerationAgent()._run_foundry(
        plan={},
        golden_examples=[],
        evidence_segments=[
            {"id": "segment-1", "locator": "policy.txt:p1", "text": "evidence"}
        ],
        count=1,
    )
    assert generated[0]["evidence_refs"] == ["policy.txt:p1"]
