import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from cloud.bedrock import Bedrock, ROLES, _access_test_png, _require_test_response, load_environment


class BedrockTests(unittest.TestCase):
    def test_environment_precedence_and_role_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text(
                "AWS_REGION=us-west-2\nBEDROCK_LLM_MODEL_ID=file-model\n", encoding="utf-8")
            with patch("cloud.bedrock.ROOT", Path(directory)), patch.dict(os.environ, {
                "AWS_REGION": "us-east-1", "BEDROCK_DOCTOR_MODEL_ID": "doctor-override"
            }, clear=True):
                cloud = Bedrock()
                self.assertEqual(cloud.region, "us-east-1")
                self.assertEqual(cloud.models["doctor"], "doctor-override")
                self.assertEqual(cloud.models["routing"], "file-model")
                self.assertEqual(cloud.models["guidance_review"], "file-model")
                self.assertEqual(cloud.models["lab"], "file-model")
                self.assertEqual(cloud.models["radiology"], "file-model")
                self.assertEqual(cloud.models["ecg"], "file-model")
                self.assertEqual(set(cloud.models), set(ROLES))
                self.assertIsNone(cloud._session)  # Local configuration does not resolve credentials.

    def test_access_image_is_a_png(self):
        image = _access_test_png()
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(image), 50)

    def test_access_check_accepts_complete_or_token_limited_output(self):
        for reason in ("end_turn", "max_tokens"):
            _require_test_response({"stopReason": reason, "output": {
                "message": {"content": [{"text": "connected"}]}}}, "model")
        with self.assertRaises(ValueError):
            _require_test_response({"stopReason": "guardrail_intervened"}, "model")

    @patch("cloud.bedrock.load_environment")
    def test_rerank_uses_agent_runtime_and_region_arn(self, _):
        with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}, clear=True):
            cloud = Bedrock()
            client = MagicMock()
            with patch.object(cloud, "client", return_value=client) as get_client, \
                    patch.object(cloud, "session") as session:
                session.return_value.get_partition_for_region.return_value = "aws"
                cloud.rerank("question", ["passage"], top_n=5)
                get_client.assert_called_once_with("bedrock-agent-runtime")
                request = client.rerank.call_args.kwargs["rerankingConfiguration"]["bedrockRerankingConfiguration"]
                self.assertEqual(request["numberOfResults"], 1)
                self.assertEqual(request["modelConfiguration"]["modelArn"],
                    "arn:aws:bedrock:us-west-2::foundation-model/cohere.rerank-v3-5:0")

    @patch("cloud.bedrock.load_environment")
    def test_invalid_dimensions_rejected_before_aws(self, _):
        with patch.dict(os.environ, {"BEDROCK_EMBEDDING_DIMENSIONS": "33"}, clear=True):
            with self.assertRaises(ValueError):
                Bedrock()


if __name__ == "__main__":
    unittest.main()
