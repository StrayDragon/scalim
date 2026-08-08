<script lang="ts">
  import { getContext } from "svelte";

  type HoverTip = {
    name: string;
    value: number;
    calls: number | null;
    x: number;
    y: number;
  };

  type Props = {
    hovered?: HoverTip | null;
    onBarClick?: (name: string) => void;
  };

  let { hovered = $bindable(null as HoverTip | null), onBarClick }: Props = $props();

  const { data, xGet, yGet, yScale } = getContext("LayerCake") as any;

  const onEnter = (event: MouseEvent, d: any) => {
    hovered = {
      name: String(d?.name ?? ""),
      value: Number(d?.total_s ?? 0),
      calls: d?.calls == null ? null : Number(d.calls),
      x: event.offsetX,
      y: event.offsetY
    };
  };

  const onMove = (event: MouseEvent) => {
    if (!hovered) return;
    hovered = { ...hovered, x: event.offsetX, y: event.offsetY };
  };

  const onLeave = () => {
    hovered = null;
  };

  const onClick = (event: MouseEvent, d: any) => {
    event.stopPropagation();
    const name = String(d?.name ?? "");
    if (!name || !onBarClick) return;
    onBarClick(name);
  };
</script>

<g class="bar-group">
  {#each $data as d, i}
    <rect
      class="group-rect cursor-pointer"
      data-id={i}
      x={0}
      y={$yGet(d)}
      height={$yScale.bandwidth()}
      width={Math.max(0, Number($xGet(d) || 0))}
      fill="#0f766e"
      opacity={hovered && hovered.name !== String(d?.name ?? "") ? 0.35 : 0.9}
      role="button"
      tabindex="0"
      aria-label={String(d?.name ?? "")}
      onmouseenter={(event) => onEnter(event, d)}
      onmousemove={onMove}
      onmouseleave={onLeave}
      onclick={(event) => onClick(event, d)}
      onkeydown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick(event as unknown as MouseEvent, d);
        }
      }}
    ></rect>
  {/each}
</g>
