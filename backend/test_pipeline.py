"""Offline tests: every preset runs through the real pipeline in mock mode (no AWS calls).

Run from the repo root:  .venv/bin/python -m unittest backend.test_pipeline -v
"""
import asyncio
import unittest

from backend.events import TERMINAL_TYPES, RunLog
from backend.fixtures import PRESETS
from backend.guardrail import Guard
from backend.pipeline import run_pipeline

REQUIRED_KEYS = {"event_id", "run_id", "sequence", "timestamp", "type", "summary", "visibility", "payload"}


def run(preset_id: str) -> list[dict]:
    log = RunLog("run-test", preset_id)
    asyncio.run(run_pipeline(log, PRESETS[preset_id], "mock", Guard(enabled=False)))
    return log.events


def types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


class PipelineTests(unittest.TestCase):
    def test_every_event_has_the_keys_the_frontend_needs(self):
        for preset_id in PRESETS:
            for event in run(preset_id):
                self.assertTrue(REQUIRED_KEYS <= event.keys(), event["type"])
                self.assertIn(event["visibility"], {"patient", "demo_detail", "operator"})

    def test_sequences_are_contiguous_and_ids_unique(self):
        for preset_id in PRESETS:
            events = run(preset_id)
            self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))
            self.assertEqual(len({e["event_id"] for e in events}), len(events))

    def test_exactly_one_terminal_event_and_it_is_last(self):
        for preset_id in PRESETS:
            events = run(preset_id)
            terminal = [e for e in events if e["type"] in TERMINAL_TYPES]
            self.assertEqual(len(terminal), 1)
            self.assertIs(events[-1], terminal[0])

    def test_standard_case_completes_with_four_sections(self):
        events = run("demo-001")
        self.assertEqual(events[-1]["type"], "run.completed")
        self.assertEqual(types(events).count("answer.section"), 4)

    def test_red_flag_pauses_and_withholds_every_section(self):
        events = run("demo-002")
        self.assertEqual(events[-1]["type"], "run.paused")
        self.assertIn("review.required", types(events))
        self.assertNotIn("answer.section", types(events))
        flagged = [e for e in events if e["type"] == "worker.completed" and e["payload"]["red_flags"]]
        self.assertEqual([e["node"] for e in flagged], ["ecg"])
        self.assertEqual(flagged[0]["payload"]["red_flags"][0]["flag_id"], "flag-spo2")

    def test_missing_imaging_fails_that_step_and_ends_partial(self):
        events = run("demo-003")
        failed = [e for e in events if e["type"] == "worker.failed"]
        self.assertEqual([e["node"] for e in failed], ["radiology"])
        self.assertEqual(failed[0]["payload"]["error_category"], "missing_input")
        self.assertEqual(events[-1]["type"], "run.partial")

    def test_the_stop_does_not_depend_on_the_model(self):
        # In mock mode no model is used at all, and the red flag still fires: the gate is plain code.
        self.assertEqual(run("demo-002")[-1]["type"], "run.paused")


if __name__ == "__main__":
    unittest.main()
