"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DownloadButtonProps {
  url: string;
  label: string;
  filename?: string;
}

export function DownloadButton({ url, label, filename }: DownloadButtonProps) {
  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = url;
    if (filename) a.download = filename;
    a.click();
  };

  return (
    <Button variant="outline" onClick={handleDownload} size="sm">
      <Download className="mr-2 h-4 w-4" />
      {label}
    </Button>
  );
}
