import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tide disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-deep text-white hover:bg-tide",
        gold: "bg-[#c4a574] text-deep hover:bg-[#b08958]",
        ghost: "border border-line bg-white/80 text-ink hover:border-tide",
        danger: "bg-[#7d2f2f] text-white hover:bg-[#9b3a3a]",
      },
      size: {
        md: "min-h-12",
        sm: "min-h-10 px-4 text-xs",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonStyles>) {
  return <button className={cn(buttonStyles({ variant, size }), className)} {...props} />;
}
