<script lang="ts">
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "$utils/cn";

  export let className: string = "";
</script>

<DialogPrimitive.Title class={cn("text-sm font-semibold text-foreground", className)} {...$$restProps}>
  <slot />
</DialogPrimitive.Title>
