import { cn } from "@/lib/utils";
import type { InputHTMLAttributes } from "react";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "min-h-12 w-full rounded-2xl border border-line bg-white px-4 text-sm outline-none focus:border-tide",
        className,
      )}
      {...props}
    />
  );
}
