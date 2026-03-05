<script lang="ts">
  import { cn } from "$utils/cn";

  export let variant: "default" | "secondary" | "outline" | "success" | "warning" | "destructive" = "default";
  export let className: string = "";

  const base =
    "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors";

  const variants: Record<typeof variant, string> = {
    default: "border-transparent bg-primary text-primary-foreground",
    secondary: "border-transparent bg-secondary text-secondary-foreground",
    outline: "border-border text-foreground",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    destructive: "border-red-200 bg-red-50 text-red-600"
  };
</script>

<span class={cn(base, variants[variant], className)} {...$$restProps}>
  <slot />
</span>
