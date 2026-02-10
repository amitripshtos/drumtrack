import { UploadForm } from "@/components/upload-form";

export default function HomePage() {
  return (
    <main className="flex flex-col items-center justify-center p-8 min-h-[calc(100vh-2rem)]">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-2">DrumTrack</h1>
        <p className="text-muted-foreground">
          Isolate drums from any song and generate a MIDI drum track
        </p>
      </div>
      <UploadForm />
    </main>
  );
}
