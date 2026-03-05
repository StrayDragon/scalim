<script lang="ts">
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "$utils/cn";
  export let className: string = "";
</script>

<DialogPrimitive.Close
  class={cn(
    "inline-flex items-center justify-center rounded-md border border-input bg-background px-2 py-1 text-[11px]",
    "text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors",
    className
  )}
  {...$$restProps}
>
  <slot />
</DialogPrimitive.Close>
