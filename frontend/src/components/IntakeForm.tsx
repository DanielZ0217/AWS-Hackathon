import { useState } from "react";
import type { FormEvent } from "react";
import type { ConnectionStatus } from "../source/types";
import type { RunSubmission, UploadModality } from "../source/liveSource";
import { buttonPrimary } from "./buttonStyles";

interface Props {
  status: ConnectionStatus;
  onSubmit: (submission: RunSubmission) => void;
}

const labels: Record<UploadModality, string> = {
  lab_report: "Lab report",
  radiology_image: "X-ray or radiology image",
  ecg_image: "ECG image",
};

export function IntakeForm({ status, onSubmit }: Props) {
  const [patientText, setPatientText] = useState("");
  const [files, setFiles] = useState<Array<{ file: File; modality: UploadModality }>>([]);
  const running = status === "connecting" || status === "live";

  const chooseFiles = (selected: FileList | null) => {
    setFiles(Array.from(selected ?? []).slice(0, 10).map((file) => ({
      file,
      modality: (file.type.startsWith("image/") ? "radiology_image" : "lab_report") as UploadModality,
    })));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!patientText.trim() && files.length === 0) return;
    onSubmit({
      patientText: patientText.trim(),
      requestedOutcomes: ["understand_tests", "combined_explanation"],
      files,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-5 rounded-2xl border border-line bg-white p-5 shadow-sm">
      <div>
        <label htmlFor="patient-question" className="block font-bold">What would you like help understanding?</label>
        <textarea id="patient-question" rows={4} value={patientText}
          onChange={(event) => setPatientText(event.target.value)}
          placeholder="Describe your question, symptoms, or what you want explained."
          className="mt-2 w-full rounded-xl border border-line bg-paper px-3 py-2 text-ink outline-none focus:ring-2 focus:ring-focus" />
      </div>

      <div>
        <label htmlFor="patient-files" className="block font-bold">Add reports or images</label>
        <p className="mt-1 text-sm text-ink-soft">PNG, JPEG, WebP, GIF, JSON, Markdown, or text. Up to 10 files; images up to 3.75 MB.</p>
        <input id="patient-files" type="file" multiple
          accept="image/png,image/jpeg,image/webp,image/gif,application/json,text/plain,text/markdown,.md,.txt,.json"
          onChange={(event) => chooseFiles(event.target.files)}
          className="mt-2 block w-full rounded-xl border border-dashed border-line bg-paper px-3 py-3" />
      </div>

      {files.length > 0 && (
        <ul className="space-y-2" aria-label="Selected files">
          {files.map((item, index) => (
            <li key={`${item.file.name}-${index}`} className="flex flex-col gap-2 rounded-xl bg-paper p-3 sm:flex-row sm:items-center sm:justify-between">
              <span className="truncate text-sm font-bold">{item.file.name}</span>
              <select aria-label={`Type for ${item.file.name}`} value={item.modality}
                onChange={(event) => setFiles((current) => current.map((entry, entryIndex) =>
                  entryIndex === index ? { ...entry, modality: event.target.value as UploadModality } : entry))}
                className="rounded-lg border border-line bg-white px-2 py-1 text-sm">
                {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </li>
          ))}
        </ul>
      )}

      <button className={buttonPrimary} type="submit"
        disabled={running || (!patientText.trim() && files.length === 0)}>
        {running ? "Care team reviewing…" : status === "ended" ? "Start another review" : "Start care team review"}
      </button>
    </form>
  );
}
