<script lang="ts">
  import DerivedFieldsEditor from "$ui/panels/DerivedFieldsEditor.svelte";

  export let yamlPath: string[] = [];
</script>

<div data-yaml-path={yamlPath.join(".")}>
  <DerivedFieldsEditor />
</div>
