<script lang="ts">
  import { Background, Controls, MiniMap, SvelteFlow, useSvelteFlow } from "@xyflow/svelte";
  import "@xyflow/svelte/dist/style.css";
  import { state, handleNodeDrag, handleNodeDragStart, handleNodeDragStop, onNodeClick, registerFlowApi } from "$domain/state.svelte";
  import SourceNode from "$nodes/SourceNode.svelte";
  import LoaderNode from "$nodes/LoaderNode.svelte";
  import FieldNode from "$nodes/FieldNode.svelte";
  import DerivedNode from "$nodes/DerivedNode.svelte";
  import PlanNode from "$nodes/PlanNode.svelte";
  import StageNode from "$nodes/StageNode.svelte";
  import StageBandNode from "$nodes/StageBandNode.svelte";

  const nodeTypes = {
    source: SourceNode,
    loader: LoaderNode,
    field: FieldNode,
    derived: DerivedNode,
    plan: PlanNode,
    stage: StageNode,
    stage_band: StageBandNode,
    ingest_band: StageBandNode
  };

  const flowApi = useSvelteFlow();
  registerFlowApi(flowApi);
</script>

<div class="absolute inset-0">
  <SvelteFlow
    bind:nodes={state.nodes}
    bind:edges={state.edges}
    fitView
    nodeTypes={nodeTypes}
    class="bg-transparent"
    onnodeclick={onNodeClick}
    onnodedragstart={handleNodeDragStart}
    onnodedrag={handleNodeDrag}
    onnodedragstop={handleNodeDragStop}
  >
    <Background />
    <MiniMap />
    <Controls />
  </SvelteFlow>
</div>
