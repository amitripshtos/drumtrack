"use client";

import { Loader2, Upload, Youtube } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { submitYouTube, uploadFile } from "@/lib/api";
import type { JobResponse } from "@/types";

export function UploadForm() {
  const router = useRouter();
  const [mode, setMode] = useState<"upload" | "youtube">("upload");
  const [bpmMode, setBpmMode] = useState<"auto" | "manual">("auto");
  const [bpm, setBpm] = useState("120");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFile(accepted[0]);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "audio/mpeg": [".mp3"],
      "audio/wav": [".wav"],
      "audio/mp4": [".m4a"],
      "audio/x-m4a": [".m4a"],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const handleSubmit = async () => {
    let bpmValue: number | undefined;
    if (bpmMode === "manual") {
      const bpmNum = parseFloat(bpm);
      if (Number.isNaN(bpmNum) || bpmNum < 20 || bpmNum > 300) {
        setError("BPM must be between 20 and 300");
        return;
      }
      bpmValue = bpmNum;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      let job: JobResponse;
      if (mode === "upload") {
        if (!file) {
          setError("Please select a file");
          setIsSubmitting(false);
          return;
        }
        job = await uploadFile(file, bpmValue);
      } else {
        if (!youtubeUrl.trim()) {
          setError("Please enter a YouTube URL");
          setIsSubmitting(false);
          return;
        }
        job = await submitYouTube(youtubeUrl.trim(), bpmValue);
      }
      router.push(`/job/${job.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-lg">
      <CardHeader>
        <CardTitle>Upload a Song</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Mode toggle */}
        <div className="flex gap-2">
          <Button
            variant={mode === "upload" ? "default" : "outline"}
            onClick={() => setMode("upload")}
            className="flex-1"
          >
            <Upload className="mr-2 h-4 w-4" />
            Upload MP3
          </Button>
          <Button
            variant={mode === "youtube" ? "default" : "outline"}
            onClick={() => setMode("youtube")}
            className="flex-1"
          >
            <Youtube className="mr-2 h-4 w-4" />
            YouTube URL
          </Button>
        </div>

        {/* File upload or YouTube URL */}
        {mode === "upload" ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : file
                  ? "border-green-500 bg-green-500/5"
                  : "border-muted-foreground/25 hover:border-muted-foreground/50"
            }`}
          >
            <input {...getInputProps()} />
            {file ? (
              <p className="text-sm text-green-600 font-medium">{file.name}</p>
            ) : isDragActive ? (
              <p className="text-sm text-muted-foreground">Drop the file here</p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Drag & drop an MP3/M4A here, or click to select
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <Label htmlFor="youtube-url">YouTube URL</Label>
            <Input
              id="youtube-url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
            />
          </div>
        )}

        {/* BPM input */}
        <div className="space-y-2">
          <Label>BPM (Tempo)</Label>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={bpmMode === "auto" ? "default" : "outline"}
              onClick={() => setBpmMode("auto")}
              className="flex-1"
              size="sm"
            >
              Auto Detect
            </Button>
            <Button
              type="button"
              variant={bpmMode === "manual" ? "default" : "outline"}
              onClick={() => setBpmMode("manual")}
              className="flex-1"
              size="sm"
            >
              Manual
            </Button>
          </div>
          {bpmMode === "manual" ? (
            <Input
              id="bpm"
              type="number"
              min={20}
              max={300}
              value={bpm}
              onChange={(e) => setBpm(e.target.value)}
              placeholder="120"
            />
          ) : (
            <p className="text-xs text-muted-foreground">
              BPM will be automatically detected from the audio
            </p>
          )}
        </div>

        {/* Error */}
        {error && <p className="text-sm text-red-500">{error}</p>}

        {/* Submit */}
        <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full">
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            "Start Processing"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
