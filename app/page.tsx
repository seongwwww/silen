import { RecordForm } from "./_components/RecordForm";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-svh max-w-md flex-col justify-center p-4">
      <h1 className="mb-3 text-lg font-medium">오늘, 실은</h1>
      <RecordForm />
    </main>
  );
}
