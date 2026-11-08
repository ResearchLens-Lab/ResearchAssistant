import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-50 p-4 text-center space-y-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-200 text-zinc-700">
        <FileQuestion className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-bold text-zinc-900">404 - Page Not Found</h2>
        <p className="text-xs text-zinc-500 max-w-sm">
          The requested research view or resource could not be found.
        </p>
      </div>
      <Button variant="workbench" size="sm" asChild>
        <Link href="/papers">Return to Library</Link>
      </Button>
    </div>
  );
}
