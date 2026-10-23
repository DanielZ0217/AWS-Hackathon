# MIMIC–NIH longitudinal composite cohort (v1)

39 **composite virtual patients** (104 time points) for the AWS Agentic AI Hackathon (Healthcare / Caregivers track).
Each virtual patient has **2–3 time points**. Every time point has one 12-lead ECG and one frontal chest X-ray.
Trends: **improving** 8, **worsening** 15, **not improving** 16.

Only patients whose ECG and X-ray severity tiers are **identical at every time point** are kept.
11 off-by-one patients (VP02, 03, 05, 06, 07, 08, 11, 12, 15, 21, 23) were moved to `excluded/` with their own CSVs.
Patient IDs were not renumbered, so the numbers have gaps.

> Prototype data for an AI demo. Not for clinical use, not medical advice.

## Files

| File | Content |
|---|---|
| `patients.csv` | One row per virtual patient: trend, days, age/sex, ECG and X-ray tier sequences, a one-line story, provenance |
| `metadata.csv` | One row per time point: file paths, ECG machine report, heart rate, PR/QRS/QT (ms), QRS axis, X-ray labels and view, severity tiers, source IDs and URLs |
| `patients/VPxx/t<k>_day<d>/` | `<study_id>.hea` + `<study_id>.dat` (WFDB ECG) and `<image>.png` (X-ray) |

Read an ECG: `wfdb.rdrecord("patients/VP01/t0_day0/<study_id>")` gives `p_signal` with shape (5000, 12) in millivolts, 500 Hz, 10 s, leads I, II, III, aVR, aVF, aVL, V1–V6.
X-rays are 1024×1024 grayscale PNG.

## How the patients were built

1. **ECG sequences** come from one real MIMIC-IV-ECG patient each: 2–3 ECGs, 1–14 days apart, at most 28 days in total, one ECG per day.
   The time gaps are **real**. MIMIC shifts dates per patient but keeps the intervals.
2. **X-ray sequences** come from one real NIH ChestX-ray14 patient each: 2–3 frontal images in follow-up order (at most 2 skipped follow-ups), with the same view (PA or AP) throughout, age 40 or older.
   NIH has **no dates**, so each X-ray is placed on the day of the matching ECG.
3. **Severity tiers** (0–3) are assigned by text rules:

| Tier | ECG (MIMIC machine report) | X-ray (NIH labels) |
|---|---|---|
| 0 | "Normal ECG" + sinus rhythm, heart rate 50–100 | No Finding |
| 1 | AF/flutter (controlled or slow), old infarct ("age undetermined"), LVH, bundle branch block | Cardiomegaly, no fluid |
| 2 | AF/flutter with rapid or uncontrolled rate, "may be due to myocardial ischemia", tachycardia (sinus ≥110 bpm, SVT, VT) | Cardiomegaly + pleural effusion |
| 3 | "Consider acute ST elevation MI", "consider acute infarct", any "injury" statement | Cardiomegaly + pulmonary edema |

4. **Matching rules**:
   - Same number of time points and the same trend in both modalities.
   - The change has the same direction (better, same, worse) at every step.
   - The tiers differ by at most 1 at every time point; exact matches were preferred (see `exact_tier_match` in `patients.csv`).
   - X-ray stories are cardiac only: cardiomegaly is present at every abnormal time point, because a heart doesn't shrink to normal or newly enlarge within days, and only the fluid changes. Images with unrelated findings (mass, nodule, pneumothorax, fibrosis, hernia, emphysema, pneumonia, consolidation) were excluded.
   - ECGs whose machine report flags poor quality ("data quality", "lead reversal", "unsuitable", "artifact", partial leads) and ECGs about pericarditis or hyperkalemia were excluded.
   - Every ECG file was checked after download: 12 leads × 5000 samples, no missing values, no flat lead.
   - Each source patient is used only once.

## Limitations (please keep these visible in any demo)

- **Each virtual patient is two different real people.** The ECG and X-ray don't come from the same body. Age and sex shown are the X-ray patient's; MIMIC-IV-ECG has no open age/sex data.
- **The ECG text is machine-generated**, not confirmed by a cardiologist. Automated "acute MI" statements often flag things that aren't heart attacks.
- **NIH labels were mined from radiology reports by an NLP tool**, and the original paper reports some label noise.
- **Severity tiers are rule-based**, not clinically validated. They make the pairs approximately coherent, not equivalent.
- X-ray timing is assigned; only the ECG time gaps are real.

## Sources and licenses

- **MIMIC-IV-ECG v1.0**, PhysioNet: https://physionet.org/content/mimic-iv-ecg/1.0/ (open access, Open Database License). Cite Gow B. et al., MIMIC-IV-ECG (PhysioNet) and the PhysioNet standard citation.
- **NIH ChestX-ray14**, NIH Clinical Center: https://nihcc.app.box.com/v/ChestXray-NIHCC (images taken from the Hugging Face mirror `alkzar90/NIH-Chest-X-ray-dataset`). Cite Wang X. et al., "ChestX-ray8", CVPR 2017, and acknowledge the NIH Clinical Center as the data provider.

## Rebuild

From `cohort/`: `python 02_match_longitudinal.py` (rank candidates), then `python 03_build_dataset.py` (download, validate, assemble).
Inputs: `data/raw/mimic/machine_measurements.csv`, `data/raw/Data_Entry_2017_v2020.csv`.
