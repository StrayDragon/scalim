<script lang="ts">
  import { Collapsible as CollapsiblePrimitive } from "bits-ui";
  import { cn } from "$utils/cn";
  export let className: string = "";
</script>

<CollapsiblePrimitive.Content
  class={cn(
    "overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down",
    className
  )}
  {...$$restProps}
>
  <slot />
</CollapsiblePrimitive.Content>
