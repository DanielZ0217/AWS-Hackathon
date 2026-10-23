import tempfile
import unittest
from pathlib import Path

from backend.knowledge import LocalReferenceProvider
from backend.schemas import RunRequest, WorkflowEvent
from backend.store import Journal
from backend.workflow import WorkflowEngine


ROOT = Path(__file__).resolve().parents[2]


class JournalTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_sequence_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "events.sqlite3")
            journal.create_run("run-1", WorkflowEvent.now(), {"patient_text": "question"})
            common = dict(run_id="run-1", sequence=0, trace_id="trace-1", span_id="span-1",
                          timestamp=WorkflowEvent.now(), layer="runtime", node="run",
                          status="running", summary="test")
            first = await journal.append(WorkflowEvent(event_id="event-1", type="run.started", **common))
            second = await journal.append(WorkflowEvent(event_id="event-2", type="intake.started", **common))
            duplicate = await journal.append(WorkflowEvent(event_id="event-2", type="intake.started", **common))
            self.assertEqual((first.sequence, second.sequence, duplicate.sequence), (1, 2, 2))
            self.assertEqual([event.event_id for event in journal.events_after("run-1", 1)], ["event-2"])
            journal.close()


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_synthetic_case_streams_and_pauses_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "workflow.sqlite3")
            engine = WorkflowEngine(
                journal, LocalReferenceProvider(ROOT / "sample-data" / "s3" / "reference"), ROOT)
            request = RunRequest(
                patient_text="I am short of breath and have ankle swelling. What do these tests mean?",
                artifacts=[
                    {"artifact_id": "lab", "filename": "labs.json", "media_type": "application/json",
                     "storage_reference": "sample-data/s3/patient/fictional-001/labs.json",
                     "modality": "lab_report", "modality_source": "user_label"},
                    {"artifact_id": "xray", "filename": "xray.md", "media_type": "text/markdown",
                     "storage_reference": "sample-data/s3/patient/fictional-001/chest-xray-report.md",
                     "modality": "radiology_image", "modality_source": "user_label"},
                    {"artifact_id": "ecg", "filename": "ecg.md", "media_type": "text/markdown",
                     "storage_reference": "sample-data/s3/patient/fictional-001/ecg-report.md",
                     "modality": "ecg_image", "modality_source": "user_label"},
                ],
                requested_outcomes=["understand_tests", "combined_explanation"],
                knowledge_snapshot={"corpus_version": "test-v1"},
            )
            now = WorkflowEvent.now()
            journal.create_run("run-demo", now, request.model_dump(mode="json"))
            await engine.run("run-demo", request)
            record = journal.get_run("run-demo")
            self.assertEqual(record["status"], "needs_human_review")
            event_types = [event.type for event in journal.events_after("run-demo", 0)]
            self.assertIn("intake.decomposed", event_types)
            self.assertEqual(event_types.count("worker.started"), 3)
            self.assertIn("doctor.review_completed", event_types)
            self.assertIn("review.required", event_types)
            self.assertIn("answer.section", event_types)
            self.assertEqual(event_types[-1], "run.needs_human_review")
            self.assertTrue(record["state"]["final_response"])
            journal.close()


if __name__ == "__main__":
    unittest.main()
