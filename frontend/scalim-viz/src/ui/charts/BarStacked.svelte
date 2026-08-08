<script lang="ts">
  import { getContext } from "svelte";

  type HoverTip = {
    seriesKey: string;
    rowLabel: string;
    value: number;
    x: number;
    y: number;
  };

  type Props = {
    hovered?: HoverTip | null;
    onRowClick?: (rowLabel: string) => void;
  };

  let { hovered = $bindable(null as HoverTip | null), onRowClick }: Props = $props();

  const { data, xGet, yGet, zGet, yScale } = getContext("LayerCake") as any;

  const seriesWidth = (d: any) => {
    const xVals = $xGet(d);
    return Math.max(0, Number(xVals[1]) - Number(xVals[0]));
  };

  const onEnter = (event: MouseEvent, series: any, d: any) => {
    const value = Number(d[1]) - Number(d[0]);
    hovered = {
      seriesKey: String(series?.key ?? ""),
      rowLabel: String(d?.data?.row ?? ""),
      value,
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
    const rowLabel = String(d?.data?.row ?? "");
    if (!rowLabel || !onRowClick) return;
    onRowClick(rowLabel);
  };
</script>

<g class="bar-group">
  {#each $data as series}
    {#each series as d, i}
      <rect
        class="group-rect cursor-pointer"
        data-id={i}
        x={$xGet(d)[0]}
        y={$yGet(d)}
        height={$yScale.bandwidth()}
        width={seriesWidth(d)}
        fill={$zGet(series)}
        opacity={hovered && hovered.seriesKey && hovered.seriesKey !== String(series?.key) ? 0.35 : 0.95}
        role="button"
        tabindex="0"
        aria-label={`${String(series?.key ?? "")} ${String(d?.data?.row ?? "")}`}
        onmouseenter={(event) => onEnter(event, series, d)}
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
  {/each}
</g>
