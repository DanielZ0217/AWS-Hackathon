"""Offline contract tests; fictitious strings and mock clients are not clinical evidence."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from ingestion import pipeline as p


class FakeBedrock:
    def __init__(self, payload, stop="end_turn"):
        self.payload, self.stop = payload, stop
        self.extractions = self.embeddings = 0

    def converse(self, **kwargs):
        self.extractions += 1
        return {"stopReason": self.stop, "output": {"message": {"content": [
            {"text": json.dumps(self.payload)}, {"reasoningContent": {"text": "DO NOT SAVE"}}]}},
            "usage": {"inputTokens": 10, "outputTokens": 10}}

    def invoke_model(self, **kwargs):
        self.embeddings += 1
        size = json.loads(kwargs["body"])["dimensions"]
        return {"body": io.BytesIO(json.dumps({"embedding": [0.1] * size}).encode())}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.work = self.base / "work"
        self.text = "Fixture finding may indicate fixture condition in a test population."
        self.payload = {"nodes": [{"id": "n1", "label": "fixture finding", "type": "Finding"},
                                  {"id": "n2", "label": "fixture condition", "type": "Condition"}],
                        "edges": [{"source": "n1", "target": "n2", "relation": "MAY_INDICATE",
                                   "quote": self.text, "assertion_status": "uncertain",
                                   "qualifiers": {"population": "test population"},
                                   "uncertainty_notes": ["fixture uncertainty"]}]}
        self.write("raw.html", "<article>" + self.text + "</article>")
        self.write("sections.json", {"sections": [{"heading": "Fixture", "text": self.text,
                                                   "locator": "article"}]})
        self.write("expected.json", {"secret_expected_answer": "EXCLUDE_ME"})
        common = {"source_version": "fixture-v1", "license_reference": "test-only fixture",
                  "review": {"rights_approved": True, "content_approved": True,
                             "reviewer": "test", "reviewed_at": "2026-10-23T00:00:00Z"}}
        self.manifest = {"resources": [
            {**common, "resource_id": "ref-bnp", "role": "reference_knowledge", "path": "sections.json",
             "raw_path": "raw.html", "title": "Fixture, not the actual article",
             "source_url": "https://medlineplus.gov/lab-tests/natriuretic-peptide-tests-bnp-nt-probnp/",
             "retrieval_scopes": ["lab", "synthesis", "nutrition"]},
            {**common, "resource_id": "fixture-eval", "role": "evaluation", "path": "expected.json",
             "source_url": "synthetic:fixture", "evaluation_kind": "expected_output"}]}
        self.write("manifest.json", self.manifest)

    def write(self, name, value):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return path

    def prepare(self):
        return p.prepare(self.base / "manifest.json", self.work, "test-v1")

    def extracted(self):
        self.prepare()
        client = FakeBedrock(self.payload)
        p.extract(self.work, client, "test-model", "test-region")
        return client

    def review(self, status="accepted"):
        review = p.read(self.work / "review.template.json")
        review.update(reviewer="test reviewer", reviewed_at="2026-10-23T01:00:00Z")
        for decision in review["decisions"].values():
            decision.update(status=status, reason="Fixture supports this test assertion")
        return self.write("review.json", review)

    def test_lanes_and_idempotence(self):
        first = self.prepare()
        self.assertEqual(first, self.prepare())
        self.assertNotIn("EXCLUDE_ME", (self.work / "children.json").read_text())
        self.assertTrue(any("evaluation" in x["artifact_ref"] for x in first["resources"]))
        parent = p.read(self.work / "parents.json")[0]
        for chunk in p.read(self.work / "children.json"):
            self.assertEqual(chunk["text"], parent["text"][chunk["start"]:chunk["end"]])

    def test_unapproved_reference_and_relabelled_evaluation_fail(self):
        self.manifest["resources"][0]["review"]["content_approved"] = False
        self.write("manifest.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "Content review"):
            self.prepare()
        self.manifest["resources"][0]["review"]["content_approved"] = True
        self.manifest["resources"][1]["role"] = "reference_knowledge"
        self.write("manifest.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            self.prepare()

    def test_mutated_input_needs_new_version(self):
        self.prepare()
        self.write("raw.html", "changed source")
        with self.assertRaisesRegex(ValueError, "different inputs"):
            self.prepare()

    def test_invalid_edges(self):
        self.prepare()
        parent = p.read(self.work / "parents.json")[0]
        for field, value, reason in [("quote", "invented passage", "Quote"),
                                     ("target", "unknown", "Dangling"),
                                     ("relation", "LOCATED_IN", "endpoint"),
                                     ("assertion_status", "certain", "assertion")]:
            with self.subTest(field=field):
                payload = copy.deepcopy(self.payload)
                payload["edges"][0][field] = value
                with self.assertRaisesRegex(ValueError, reason):
                    p.validate_extraction(payload, parent)

    def test_truncated_call_does_not_complete(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            p.extract(self.work, FakeBedrock(self.payload, "max_tokens"), "test-model", "test-region")
        self.assertFalse((self.work / "candidates.json").exists())
        self.assertEqual(len(list((self.work / "failures").glob("*.json"))), 1)

    def test_reuses_calls_and_does_not_store_reasoning(self):
        client = self.extracted()
        p.extract(self.work, client, "test-model", "test-region")
        p.embed(self.work, client, "test-region", 256)
        p.embed(self.work, client, "test-region", 256)
        self.assertEqual((client.extractions, client.embeddings), (1, 1))
        self.assertNotIn("DO NOT SAVE", (self.work / "candidates.json").read_text())

    def test_export_preserves_qualification_and_source_links(self):
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        receipt = p.export(self.work, self.review())
        self.assertEqual(receipt["clinical_assertion_count"], 1)
        self.assertEqual(receipt["status"], "staged_not_published")
        edges = (self.work / "export/neptune/edges.csv").read_text()
        self.assertIn("uncertain", edges)
        self.assertIn("test population", edges)
        self.assertIn("MENTIONS", edges)
        self.assertNotIn("EXCLUDE_ME", (self.work / "export/opensearch-bulk.ndjson").read_text())
        self.assertEqual(receipt, p.export(self.work, self.base / "review.json"))

    def test_pending_and_stale_review_block_export(self):
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        with self.assertRaisesRegex(ValueError, "Pending"):
            p.export(self.work, self.review("pending"))
        path = self.review()
        review = p.read(path)
        review["candidates_sha256"] = "wrong"
        self.write("review.json", review)
        with self.assertRaisesRegex(ValueError, "different candidates"):
            p.export(self.work, path)

    def test_causation_needs_explicit_support(self):
        self.payload["edges"][0]["relation"] = "CAUSES"
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        with self.assertRaisesRegex(ValueError, "Causal assertion"):
            p.export(self.work, self.review())

    def test_missing_vectors_block_export(self):
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        (self.work / "embeddings.json").write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Embeddings incomplete"):
            p.export(self.work, self.review())

    def test_negation_preserved(self):
        self.payload["edges"][0]["assertion_status"] = "negated"
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        p.export(self.work, self.review())
        self.assertIn("negated", (self.work / "export/neptune/edges.csv").read_text())

    def test_mapping_conflicts_rejected(self):
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        path = self.review()
        review = p.read(path)
        parent = p.read(self.work / "parents.json")[0]["id"]
        review["concept_keys"] = {parent + "/n1": "same", parent + "/n2": "same"}
        self.write("review.json", review)
        with self.assertRaisesRegex(ValueError, "conflicting types"):
            p.export(self.work, path)

    def test_reviewed_mapping_connects_passages(self):
        self.write("sections.json", {"sections": [
            {"heading": "Fixture A", "text": self.text, "locator": "section-a"},
            {"heading": "Fixture B", "text": self.text, "locator": "section-b"}]})
        client = self.extracted()
        p.embed(self.work, client, "test-region", 256)
        path = self.review()
        review = p.read(path)
        for parent in p.read(self.work / "parents.json"):
            review["concept_keys"][parent["id"] + "/n1"] = "local-test-v1:finding"
            review["concept_keys"][parent["id"] + "/n2"] = "local-test-v1:condition"
        self.write("review.json", review)
        receipt = p.export(self.work, path)
        self.assertEqual(receipt["node_count"], 4)  # Two shared concepts + two source passages.
        self.assertEqual(receipt["clinical_assertion_count"], 2)

    def test_original_tampering_detected(self):
        state = self.prepare()
        (self.work / state["resources"][0]["raw_ref"]).write_text("altered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Original reference"):
            p.stage(self.work)

    def test_model_change_requires_new_version(self):
        client = self.extracted()
        with self.assertRaisesRegex(ValueError, "Existing artifact differs"):
            p.extract(self.work, client, "different-model", "test-region")
        self.assertEqual(client.extractions, 1)


if __name__ == "__main__":
    unittest.main()
