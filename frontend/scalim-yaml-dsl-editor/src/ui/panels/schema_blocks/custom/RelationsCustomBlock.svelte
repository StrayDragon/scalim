<script lang="ts">
  import RelationsEditor from "$ui/panels/RelationsEditor.svelte";

  export let yamlPath: string[] = [];
</script>

<div data-yaml-path={yamlPath.join(".")}>
  <RelationsEditor />
</div>
