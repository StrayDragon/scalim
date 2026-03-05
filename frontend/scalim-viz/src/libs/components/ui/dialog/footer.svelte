<script lang="ts">
  import { cn } from "$utils/cn";
  export let className: string = "";
</script>

<div class={cn("flex items-center justify-end gap-2 border-t border-border px-4 py-3", className)}>
  <slot />
</div>
