<script lang="ts">
  import { Collapsible as CollapsiblePrimitive } from "bits-ui";
  import { cn } from "$utils/cn";
  export let className: string = "";
</script>

<CollapsiblePrimitive.Trigger class={cn(className)} {...$$restProps}>
  <slot />
</CollapsiblePrimitive.Trigger>
