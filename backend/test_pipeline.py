"""Offline tests on the real bundled VP01 data (mock mode: no AWS calls).

Run from the repo root:  .venv/bin/python -m unittest backend.test_pipeline -v
"""
import asyncio
import dataclasses
import unittest

from backend import ecg, redflags
from backend.cases import build_cases
from backend.events import TERMINAL_TYPES, RunLog
from backend.guardrail import Guard
from backend.pipeline import run_pipeline
from backend.store import LocalStore, load_patient

STORE = LocalStore()
PATIENT = load_patient(STORE, "VP01")
CASES = build_cases(STORE, PATIENT)
REQUIRED_KEYS = {"event_id", "run_id", "sequence", "timestamp", "type", "summary", "visibility", "payload"}


def run(case) -> list[dict]:
    log = RunLog("run-test", case.id)
    asyncio.run(run_pipeline(log, case, "mock", Guard(enabled=False)))
    return log.events


def types(events):
    return [e["type"] for e in events]


class DataTests(unittest.TestCase):
    def test_the_patient_has_three_visits_with_real_files(self):
        self.assertEqual(len(PATIENT.visits), 3)
        for v in PATIENT.visits:
            signal, fs, names = ecg.load_ecg(STORE, "VP01", v.ecg_record)
            self.assertEqual((signal.shape, fs), ((5000, 12), 500))
            self.assertEqual(STORE.read("VP01", v.xray_file)[:4], b"\x89PNG")

    def test_red_flags_fire_only_on_the_first_visit(self):
        v1, v2, v3 = PATIENT.visits
        self.assertEqual([f["field"] for f in redflags.ecg_flags(v1)[0]], ["ecg_report"])
        self.assertEqual([f["field"] for f in redflags.xray_flags(v1)], ["xray_edema"])
        for v in (v2, v3):
            self.assertEqual(redflags.ecg_flags(v)[0], [])  # "infarct - age undetermined" is not an acute flag
            self.assertEqual(redflags.xray_flags(v), [])

    def test_an_extreme_heart_rate_is_flagged(self):
        v = dataclasses.replace(PATIENT.visits[1], ecg={**PATIENT.visits[1].ecg, "hr_bpm": 170.0})
        self.assertEqual([f["field"] for f in redflags.ecg_flags(v)[0]], ["heart_rate"])

    def test_a_missing_heart_rate_is_a_gap_not_normal(self):
        ecg_data = {k: x for k, x in PATIENT.visits[1].ecg.items() if k != "hr_bpm"}
        flags, gaps = redflags.ecg_flags(dataclasses.replace(PATIENT.visits[1], ecg=ecg_data))
        self.assertEqual(flags, [])
        self.assertEqual([g["field"] for g in gaps], ["heart_rate"])


class PipelineTests(unittest.TestCase):
    def test_every_event_has_the_keys_the_frontend_needs(self):
        for case in CASES.values():
            for event in run(case):
                self.assertTrue(REQUIRED_KEYS <= event.keys(), event["type"])
                self.assertIn(event["visibility"], {"patient", "demo_detail", "operator"})

    def test_sequences_are_contiguous_ids_unique_and_one_terminal_event_last(self):
        for case in CASES.values():
            events = run(case)
            self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))
            self.assertEqual(len({e["event_id"] for e in events}), len(events))
            terminal = [e for e in events if e["type"] in TERMINAL_TYPES]
            self.assertEqual(len(terminal), 1)
            self.assertIs(events[-1], terminal[0])

    def test_visit_one_is_stopped_for_human_review_and_shows_no_summary(self):
        events = run(CASES["VP01-v1"])
        self.assertEqual(events[-1]["type"], "run.paused")
        self.assertIn("review.required", types(events))
        self.assertNotIn("answer.section", types(events))
        flagged = {e["node"]: [f["flag_id"] for f in e["payload"]["red_flags"]] for e in events if e["type"] == "worker.completed"}
        self.assertEqual(flagged, {"radiology": ["flag-xray_edema"], "ecg": ["flag-ecg_report"]})

    def test_later_visits_complete_with_four_sections_and_the_provenance_warning(self):
        for case_id in ("VP01-v2", "VP01-v3"):
            events = run(CASES[case_id])
            self.assertEqual(events[-1]["type"], "run.completed")
            self.assertEqual(types(events).count("answer.section"), 4)
            self.assertTrue(any("two different real people" in line for line in events[-1]["payload"]["limitations"]))

    def test_the_provenance_warning_is_also_on_the_stopped_run(self):
        last = run(CASES["VP01-v1"])[-1]
        self.assertTrue(any("two different real people" in line for line in last["payload"]["limitations"]))

    def test_a_missing_xray_fails_that_step_and_the_run_ends_partial(self):
        broken = dataclasses.replace(CASES["VP01-v2"], visit=dataclasses.replace(PATIENT.visits[1], xray_file="t1_day2/not_there.png"))
        events = run(broken)
        failed = [e for e in events if e["type"] == "worker.failed"]
        self.assertEqual([e["node"] for e in failed], ["radiology"])
        self.assertEqual(failed[0]["payload"]["error_category"], "missing_input")
        self.assertEqual(events[-1]["type"], "run.partial")

    def test_the_stop_does_not_depend_on_the_model(self):
        # Mock mode uses no model at all, and the red flag still fires: the gate is plain code.
        self.assertEqual(run(CASES["VP01-v1"])[-1]["type"], "run.paused")


if __name__ == "__main__":
    unittest.main()
