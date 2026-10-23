import unittest

from backend.models import BedrockModelGateway


class FakeCloud:
    def __init__(self):
        self.role = None
        self.messages = None
        self.tool_config = None

    def converse(self, role, messages, system=None, max_tokens=0, tool_config=None):
        self.role = role
        self.messages = messages
        self.tool_config = tool_config
        text = '''```json
        {"observations":[{"artifact_id":"lab","description":"BNP is reported as elevated.",
        "source_locator":"BNP row","uncertainty":"Interpret with clinical context."}],
        "limitations":[],"retrieval_query":"authoritative interpretation of elevated BNP"}
        ```'''
        return {"output": {"message": {"content": [{"text": text}]}}}


class ModelGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_specialist_uses_role_and_validates_json(self):
        cloud = FakeCloud()
        result = await BedrockModelGateway(cloud).specialist(
            "lab", "Explain the lab", {"lab": "BNP elevated"})
        self.assertEqual(cloud.role, "lab")
        self.assertEqual(result.observations[0].artifact_id, "lab")
        self.assertIn("BNP", result.retrieval_query)
        self.assertEqual(cloud.tool_config["toolChoice"]["tool"]["name"], "submit_specialist_result")

    async def test_specialist_attaches_images_to_converse_message(self):
        cloud = FakeCloud()
        await BedrockModelGateway(cloud).specialist(
            "radiology", "Explain the image", {}, images={"xray": ("png", b"png-bytes")})
        content = cloud.messages[0]["content"]
        self.assertEqual(content[-1]["image"]["format"], "png")
        self.assertEqual(content[-1]["image"]["source"]["bytes"], b"png-bytes")


if __name__ == "__main__":
    unittest.main()
