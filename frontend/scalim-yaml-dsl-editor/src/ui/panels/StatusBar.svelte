<script lang="ts">
  import Badge from "$components/ui/badge.svelte";
  import { issueCounts, state } from "$domain/state.svelte";

  const counts = $derived(() => issueCounts());
</script>

<div class="flex items-center justify-between border-t bg-white px-3 py-2 text-xs">
  <div class="flex items-center gap-2">
    <Badge variant={counts().errors ? "destructive" : "success"}>{counts().errors} errors</Badge>
    <Badge variant={counts().warnings ? "warning" : "outline"}>{counts().warnings} warnings</Badge>
    <span class="text-slate-500">strict: {state.strict ? "on" : "off"}</span>
  </div>
</div>
