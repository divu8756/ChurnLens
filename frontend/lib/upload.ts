// Browser-side upload checks. They save a round trip; the server checks everything again.
export const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB ?? 10);
export const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"];

export function uploadProblem(file: { name: string; size: number }, maxMb = MAX_UPLOAD_MB): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return "Only .csv and .xlsx files are supported. Save the sheet as CSV or Excel (.xlsx) and try again.";
  }
  if (file.size === 0) return "The file is empty.";
  if (file.size > maxMb * 1024 * 1024) {
    return `The file is larger than ${maxMb} MB. Remove unused columns or rows and try again.`;
  }
  return null;
}
