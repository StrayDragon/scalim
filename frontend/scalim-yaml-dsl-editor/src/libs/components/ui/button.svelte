<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { cn } from "$utils/cn";

  export let variant: "default" | "outline" | "secondary" | "ghost" | "add" | "danger" | "subtle" = "default";
  export let size: "sm" | "default" | "lg" | "icon" | "touch" = "sm";
  export let type: "button" | "submit" | "reset" = "button";
  export let className: string = "";

  const dispatch = createEventDispatcher<{ click: MouseEvent }>();
  const handleClick = (event: MouseEvent) => {
    dispatch("click", event);
  };

  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
    "disabled:pointer-events-none disabled:opacity-50 ring-offset-background touch-manipulation";

  const variants: Record<typeof variant, string> = {
    default: "bg-primary text-primary-foreground hover:bg-primary/90",
    outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    ghost: "hover:bg-accent hover:text-accent-foreground",
    add: "rounded-full border border-emerald-300 bg-gradient-to-br from-emerald-50 to-emerald-100 text-emerald-700 shadow-sm hover:border-emerald-400 hover:from-emerald-100 hover:to-emerald-200",
    danger: "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100",
    subtle: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-300"
  };

  const sizes: Record<typeof size, string> = {
    sm: "h-8 px-3",
    default: "h-9 px-4",
    lg: "h-10 px-6",
    icon: "h-8 w-8",
    touch: "h-11 min-h-[44px] min-w-[44px] px-4"
  };
</script>

<button {type} on:click={handleClick} class={cn(base, variants[variant], sizes[size], className)} {...$$restProps}>
  {#if variant === "add"}
    <svg viewBox="0 0 24 24" fill="none" class="h-4 w-4" aria-hidden="true">
      <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
  {/if}
  <slot />
</button>
