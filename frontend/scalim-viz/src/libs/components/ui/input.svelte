<script lang="ts">
  import { cn } from "$utils/cn";

  export let className: string = "";
  export let type: string = "text";
  export let value: string | number = "";
</script>

<input
  {type}
  bind:value
  class={cn(
    "flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm",
    "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2",
    "focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
    className
  )}
  {...$$restProps}
/>
