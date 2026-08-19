import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combina classes do Tailwind resolvendo conflitos (a ultima vence). */
export function cx(...classes: ClassValue[]) {
  return twMerge(clsx(classes));
}
