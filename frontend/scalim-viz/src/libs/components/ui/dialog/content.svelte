<script lang="ts">
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "$utils/cn";

  export let className: string = "";
</script>

<DialogPrimitive.Content
  class={cn(
    "fixed z-50 w-[320px] rounded-xl border border-border bg-background shadow-xl outline-none",
    "left-4 top-24",
    className
  )}
  {...$$restProps}
>
  <slot />
</DialogPrimitive.Content>
