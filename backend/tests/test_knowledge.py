import unittest

from backend.knowledge import BedrockKnowledgeBaseProvider


class FakeAgentRuntime:
    def __init__(self, uri):
        self.uri = uri
        self.request = None

    def retrieve(self, **request):
        self.request = request
        return {"retrievalResults": [{
            "content": {"text": "Reviewed clinical reference."},
            "location": {"s3Location": {"uri": self.uri}, "type": "S3"},
            "metadata": {"source_id": "source-1"},
            "score": 0.91,
        }]}


class FakeCloud:
    def __init__(self, uri):
        self.runtime = FakeAgentRuntime(uri)

    def client(self, service):
        assert service == "bedrock-agent-runtime"
        return self.runtime


class ManagedKnowledgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieves_only_approved_reference_prefix(self):
        cloud = FakeCloud("s3://bucket/sample-data/s3/reference/source.md")
        provider = BedrockKnowledgeBaseProvider(
            "kb-1", "s3://bucket/sample-data/s3/reference/", cloud=cloud)
        hits = await provider.search("heart failure", ["cardiology"], limit=3)
        self.assertEqual(hits[0].source_id, "source-1")
        self.assertIn("cardiology", cloud.runtime.request["retrievalQuery"]["text"])
        self.assertEqual(
            cloud.runtime.request["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"], 3)

    async def test_rejects_patient_lane_result(self):
        cloud = FakeCloud("s3://bucket/sample-data/s3/patient/patient.json")
        provider = BedrockKnowledgeBaseProvider(
            "kb-1", "s3://bucket/sample-data/s3/reference/", cloud=cloud)
        with self.assertRaisesRegex(ValueError, "unapproved source"):
            await provider.search("patient", [], limit=5)


if __name__ == "__main__":
    unittest.main()
