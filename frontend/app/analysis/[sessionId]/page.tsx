import { AnalysisView } from "@/components/analysis-view";

export default async function AnalysisPage({ params }: PageProps<"/analysis/[sessionId]">) {
  const { sessionId } = await params;
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12">
      <AnalysisView sessionId={sessionId} />
    </main>
  );
}
