<script lang="ts">
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "$utils/cn";

  export let className: string = "";
</script>

<DialogPrimitive.Description class={cn("text-[11px] text-muted-foreground", className)} {...$$restProps}>
  <slot />
</DialogPrimitive.Description>
