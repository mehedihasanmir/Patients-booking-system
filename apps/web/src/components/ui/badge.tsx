import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  booked: "bg-[#e5f6f2] text-[#0c5c52]",
  rescheduled: "bg-[#e7f0fb] text-[#1d4f91]",
  cancelled: "bg-[#f3eee8] text-[#6b5344]",
  enquiry: "bg-[#f8f1e4] text-[#8a5a12]",
  follow_up_needed: "bg-[#fff1df] text-[#8a4b08]",
  incomplete: "bg-[#eef1f2] text-[#3e5250]",
  failed: "bg-[#fde8e8] text-[#8d2b2b]",
  in_progress: "bg-[#e8fbf6] text-[#0f6e68]",
  open: "bg-[#fff1df] text-[#8a4b08]",
  done: "bg-[#e5f6f2] text-[#0c5c52]",
  completed: "bg-[#eef1f2] text-[#3e5250]",
  urgent: "bg-[#fde8e8] text-[#8d2b2b]",
  normal: "bg-[#eef1f2] text-[#3e5250]",
};

export function Badge({ value }: { value: string }) {
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", tones[value] ?? tones.enquiry)}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
