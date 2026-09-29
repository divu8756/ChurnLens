import { BackendStatus } from "./backend-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-16">
      <h1 className="text-3xl font-semibold">ChurnLens</h1>
      <p className="text-gray-600">
        Upload customer data and get a full churn analysis: cleaning, statistics, risk scores
        and recommended actions.
      </p>
      <BackendStatus />
    </main>
  );
}
