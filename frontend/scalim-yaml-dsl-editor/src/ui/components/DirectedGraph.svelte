<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { layoutLayered, type DirectedGraph, type GraphEdge, type GraphNode } from "$services/graph_model";

  type Props = {
    graph: DirectedGraph;
    rootIds?: string[];
    selectedPath?: string | null;
    title?: string;
  };

  let { graph, rootIds = [], selectedPath = null, title = "" }: Props = $props();

  const dispatch = createEventDispatcher<{
    select: { kind: "node" | "edge"; id: string; path?: string };
  }>();

  const layout = $derived(() => layoutLayered(graph, { rootIds }));

  const nodeClass = (n: GraphNode, selected: boolean): string => {
    const sev = n.severity || "ok";
    const base = "transition-colors";
    const selectedPart = selected ? " stroke-sky-500" : "";
    if (sev === "error") return base + " fill-red-50 stroke-red-300" + selectedPart;
    if (sev === "warning") return base + " fill-amber-50 stroke-amber-300" + selectedPart;
    if (n.kind === "main") return base + " fill-sky-50 stroke-sky-300" + selectedPart;
    return base + " fill-white stroke-slate-200" + selectedPart;
  };

  const edgeClass = (e: GraphEdge, selected: boolean): string => {
    const sev = e.severity || "ok";
    const base = "fill-none transition-colors";
    if (selected) return base + " stroke-sky-500";
    if (sev === "error") return base + " stroke-red-300";
    if (sev === "warning") return base + " stroke-amber-300";
    return base + " stroke-slate-300";
  };

  const markerIdFor = (e: GraphEdge, selected: boolean): string => {
    if (selected) return "arrow-sel";
    const sev = e.severity || "ok";
    if (sev === "error") return "arrow-err";
    if (sev === "warning") return "arrow-warn";
    return "arrow-ok";
  };

  const isSelected = (path?: string): boolean => {
    if (!path || !selectedPath) return false;
    return selectedPath === path || selectedPath.startsWith(path + ".");
  };

  const edgePath = (from: { x: number; y: number; w: number; h: number }, to: { x: number; y: number; w: number; h: number }): string => {
    const x1 = from.x + from.w;
    const y1 = from.y + from.h / 2;
    const x2 = to.x;
    const y2 = to.y + to.h / 2;
    const dx = Math.max(24, Math.abs(x2 - x1) * 0.55);
    const c1x = x1 + dx;
    const c1y = y1;
    const c2x = x2 - dx;
    const c2y = y2;
    return `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;
  };
</script>

<div class="rounded-lg border bg-white">
  {#if title}
    <div class="border-b bg-slate-50 px-3 py-2 text-[11px] text-slate-600">{title}</div>
  {/if}
  <div class="overflow-auto p-2">
    <svg
      viewBox={`0 0 ${layout().width} ${layout().height}`}
      width={layout().width}
      height={layout().height}
      class="min-w-full"
      role="img"
      aria-label="graph"
    >
      <defs>
        <marker id="arrow-ok" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" class="fill-slate-300"></path>
        </marker>
        <marker id="arrow-warn" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" class="fill-amber-300"></path>
        </marker>
        <marker id="arrow-err" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" class="fill-red-300"></path>
        </marker>
        <marker id="arrow-sel" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" class="fill-sky-500"></path>
        </marker>
      </defs>

      {#each graph.edges as e (e.id)}
        {#if layout().nodePos[e.from] && layout().nodePos[e.to]}
          {@const from = layout().nodePos[e.from]}
          {@const to = layout().nodePos[e.to]}
          {@const selected = isSelected(e.path)}
          <path
            d={edgePath(from, to)}
            class={edgeClass(e, selected)}
            stroke-width="1.5"
            marker-end={`url(#${markerIdFor(e, selected)})`}
            role="button"
            tabindex="0"
            aria-label={e.label || e.id}
            onclick={() => dispatch("select", { kind: "edge", id: e.id, path: e.path })}
            onkeydown={(ev) => {
              const key = (ev as KeyboardEvent).key;
              if (key !== "Enter" && key !== " ") return;
              ev.preventDefault();
              dispatch("select", { kind: "edge", id: e.id, path: e.path });
            }}
            style="cursor:pointer"
          >
            <title>{e.label || e.id}</title>
          </path>
        {/if}
      {/each}

      {#each graph.nodes as n (n.id)}
        {#if layout().nodePos[n.id]}
          {@const pos = layout().nodePos[n.id]}
          {@const selected = isSelected(n.path)}
          <g
            transform={`translate(${pos.x},${pos.y})`}
            role="button"
            tabindex="0"
            aria-label={n.label}
            onclick={() => dispatch("select", { kind: "node", id: n.id, path: n.path })}
            onkeydown={(ev) => {
              const key = (ev as KeyboardEvent).key;
              if (key !== "Enter" && key !== " ") return;
              ev.preventDefault();
              dispatch("select", { kind: "node", id: n.id, path: n.path });
            }}
            style="cursor:pointer"
          >
            <rect rx="10" ry="10" width={pos.w} height={pos.h} class={nodeClass(n, selected)} stroke-width="1.5"></rect>
            <text x="12" y="18" class="fill-slate-800 text-[11px] font-semibold">
              {n.label}
            </text>
            <text x="12" y="34" class="fill-slate-500 text-[10px]">
              {n.kind === "main" ? "main_source" : n.kind === "source" ? "source" : n.kind === "derived" ? "derived" : n.kind === "input" ? "input" : "unknown"}
            </text>
            <title>{n.path || n.id}</title>
          </g>
        {/if}
      {/each}
    </svg>
  </div>
</div>
