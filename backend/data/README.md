# Bundled demo data

`patients/VP01/` is one virtual patient from the **MIMIC-NIH longitudinal composite cohort (v1)** prepared for the
AWS Agentic AI Hackathon (Healthcare / Caregivers track). Three visits (day 0, 2, 3). Each visit has one 12-lead ECG
(WFDB `.hea` + `.dat`, 500 Hz, 10 s) and one frontal chest X-ray (1024x1024 PNG). `patient.json` was built from the
cohort's own `patients.csv` and `metadata.csv`.

## Limitations (keep these visible in any demo)
- **Each virtual patient is two different real people.** The ECG and the X-ray are not from the same body. Age and sex
  are the X-ray patient's.
- **The ECG report text is machine-generated**, not confirmed by a cardiologist. Automated "acute MI / injury"
  statements often flag things that are not heart attacks.
- **The X-ray labels were mined from radiology reports by an NLP tool** and contain some noise.
- The cohort's severity tiers are rule-based and not clinically validated. They are stored in `patient.json` for
  provenance only and are never shown to the models.
- X-ray timing is assigned (placed on the day of the matching ECG). Only the ECG time gaps are real.
- Prototype data for an AI demo. Not for clinical use, not medical advice.

## Sources and licenses
- **MIMIC-IV-ECG v1.0**, PhysioNet, open access, Open Database License:
  https://physionet.org/content/mimic-iv-ecg/1.0/ . Cite Gow B. et al., MIMIC-IV-ECG, and the PhysioNet standard citation.
- **NIH ChestX-ray14**, NIH Clinical Center: https://nihcc.app.box.com/v/ChestXray-NIHCC . Cite Wang X. et al.,
  "ChestX-ray8", CVPR 2017, and acknowledge the NIH Clinical Center as the data provider.

## Layout (the same keys are used in S3, one bucket per patient)
```
patients/VP01/patient.json
patients/VP01/t0_day0/<ecg_study_id>.hea|.dat
patients/VP01/t0_day0/<nih_image>.png
```
