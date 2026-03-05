<script lang="ts">
  import { cn } from "$utils/cn";
  export let className: string = "";
</script>

<label class={cn("text-[11px] font-medium text-muted-foreground", className)} {...$$restProps}>
  <slot />
</label>
