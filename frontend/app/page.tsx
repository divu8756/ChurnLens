import { BackendStatus } from "./backend-status";
import { UploadPanel } from "@/components/upload-panel";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10 sm:py-16">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">ChurnLens</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Upload customer data and get a full churn analysis: cleaning, statistics, risk scores and recommended
          actions.
        </p>
        <BackendStatus />
      </div>
      <UploadPanel />
    </main>
  );
}
