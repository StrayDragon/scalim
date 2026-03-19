<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import OutputFieldsEditor from "$ui/panels/OutputFieldsEditor.svelte";
  import { revealInYaml, state as appState } from "$domain/state.svelte";
  import { lookupYamlLocation } from "$services/yaml_doc";

  export let yamlPath: string[] = [];

  const yamlKey = () => yamlPath.join(".");
  const outputIndex = () => {
    if (yamlPath.length >= 2 && yamlPath[0] === "outputs" && /^\\d+$/.test(String(yamlPath[1]))) return Number(yamlPath[1]);
    return null;
  };

  const jumpToRaw = () => {
    const loc = lookupYamlLocation(yamlKey(), appState.yamlLocations);
    if (!loc) return;
    revealInYaml(loc.line, loc.column);
  };
</script>

{#if outputIndex() === 0}
  <OutputFieldsEditor />
{:else}
  <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
    <div class="flex items-center justify-between gap-2">
      <div class="min-w-0 truncate">
        Schema blocks: <span class="font-mono">{yamlKey()}</span> 暂不支持 index != 0 的 Output Fields 自定义编辑器
      </div>
      <Button variant="outline" size="sm" on:click={jumpToRaw}>Raw YAML</Button>
    </div>
  </div>
{/if}

