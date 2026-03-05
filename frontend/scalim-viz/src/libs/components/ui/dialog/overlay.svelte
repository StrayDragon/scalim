<script lang="ts">
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { cn } from "$utils/cn";

  export let className: string = "";
</script>

<DialogPrimitive.Overlay
  class={cn("fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm", className)}
  {...$$restProps}
/>
