<script lang="ts">
  import MainSourceFieldsEditor from "$ui/panels/MainSourceFieldsEditor.svelte";

  export let yamlPath: string[] = [];
</script>

<div data-yaml-path={yamlPath.join(".")}>
  <MainSourceFieldsEditor />
</div>
