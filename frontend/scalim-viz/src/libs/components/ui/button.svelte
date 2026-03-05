<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { cn } from "$utils/cn";

  export let variant: "default" | "outline" | "secondary" | "ghost" = "default";
  export let size: "sm" | "default" | "lg" | "icon" = "sm";
  export let type: "button" | "submit" | "reset" = "button";
  export let className: string = "";

  const dispatch = createEventDispatcher<{ click: MouseEvent }>();
  const handleClick = (event: MouseEvent) => {
    dispatch("click", event);
  };

  const base =
    "inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
    "disabled:pointer-events-none disabled:opacity-50 ring-offset-background";

  const variants: Record<typeof variant, string> = {
    default: "bg-primary text-primary-foreground hover:bg-primary/90",
    outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
    secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
    ghost: "hover:bg-accent hover:text-accent-foreground"
  };

  const sizes: Record<typeof size, string> = {
    sm: "h-8 px-3",
    default: "h-9 px-4",
    lg: "h-10 px-6",
    icon: "h-8 w-8"
  };
</script>

<button {type} on:click={handleClick} class={cn(base, variants[variant], sizes[size], className)} {...$$restProps}>
  <slot />
</button>
