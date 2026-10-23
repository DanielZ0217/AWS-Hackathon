"""Reads a real 12-lead WFDB ECG, counts the beats in plain code, and draws the trace for the model.

The rate and the irregularity are computed here, not by the model. The picture is only so the
model can look at the shape of the trace.
"""
from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .store import FileStore

DRAWN_LEADS = ("I", "II", "V1", "V5")


@dataclass
class EcgSummary:
    sample_rate_hz: int
    seconds: float
    beats_detected: int
    heart_rate_bpm: float | None  # counted from lead II; None if the beats could not be found
    rr_irregularity: float | None  # variation in the gaps between beats; 0 means perfectly regular
    notes: list[str]


def load_ecg(store: FileStore, patient_id: str, record: str) -> tuple[np.ndarray, int, list[str]]:
    """Fetch the .hea and .dat files from the store and read them with wfdb."""
    import wfdb

    stem = Path(record).name
    with tempfile.TemporaryDirectory() as tmp:
        for ext in ("hea", "dat"):
            (Path(tmp) / f"{stem}.{ext}").write_bytes(store.read(patient_id, f"{record}.{ext}"))
        rec = wfdb.rdrecord(str(Path(tmp) / stem))
    return rec.p_signal, int(rec.fs), list(rec.sig_name)


def summarize(signal: np.ndarray, fs: int, names: list[str], reported_hr: float | None = None) -> EcgSummary:
    from scipy.signal import butter, filtfilt, find_peaks

    lead = signal[:, names.index("II")] if "II" in names else signal[:, 0]
    b, a = butter(2, [0.5 / (fs / 2), 25 / (fs / 2)], btype="band")
    cleaned = filtfilt(b, a, lead)
    strength = np.abs(cleaned)
    peaks, _ = find_peaks(strength, height=0.5 * strength.max(), distance=int(0.3 * fs))  # at most ~200 beats/min

    notes: list[str] = []
    seconds = signal.shape[0] / fs
    if len(peaks) < 4:
        notes.append("Too few beats were found to measure the rhythm reliably.")
        return EcgSummary(fs, seconds, len(peaks), None, None, notes)

    gaps = np.diff(peaks) / fs
    hr = float(60 / gaps.mean())
    irregularity = float(gaps.std() / gaps.mean())
    if reported_hr and abs(hr - reported_hr) / reported_hr > 0.15:
        notes.append("Counting beats on the trace gave a rate that differs from the reported rate; treat both as approximate.")
    return EcgSummary(fs, seconds, int(len(peaks)), round(hr, 1), round(irregularity, 3), notes)


def render_png(signal: np.ndarray, fs: int, names: list[str], leads: tuple[str, ...] = DRAWN_LEADS) -> bytes:
    """A black-on-white picture of a few leads. Uses Figure directly (not pyplot), so it is thread-safe."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(11, 6.5), dpi=100)
    axes = fig.subplots(len(leads), 1, sharex=True)
    t = np.arange(signal.shape[0]) / fs
    for ax, name in zip(axes, leads):
        if name in names:
            ax.plot(t, signal[:, names.index(name)], linewidth=0.8, color="black")
        ax.set_ylabel(name, rotation=0, labelpad=18, fontsize=11)
        ax.set_yticks([])
        ax.grid(True, color="#f0c4c4", linewidth=0.6)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
    axes[-1].set_xlabel("seconds")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return buf.getvalue()
