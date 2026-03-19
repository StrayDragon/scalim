<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import type { BlockAction, EditableBlock, ScalarValue } from "$schema_blocks/index";

  type Props = {
    block: EditableBlock;
    depth?: number;
    onAction: (action: BlockAction, title: string) => void;
    onJumpToYaml: (yamlPath: string[]) => void;
  };

  let { block, depth = 0, onAction, onJumpToYaml }: Props = $props();

  const isPlainObject = (value: any): boolean => {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  };

  const scalarToString = (value: ScalarValue | undefined): string => {
    if (value == null) return "";
    return String(value);
  };

  const enumValueKey = (value: ScalarValue): string => {
    if (value === null) return "null";
    if (typeof value === "string") return "s:" + value;
    if (typeof value === "number") return "n:" + String(value);
    return "b:" + (value ? "true" : "false");
  };

  const parseEnumValueKey = (key: string): ScalarValue => {
    if (key === "null") return null;
    const idx = key.indexOf(":");
    if (idx <= 0) return key;
    const t = key.slice(0, idx);
    const raw = key.slice(idx + 1);
    if (t === "n") return Number(raw);
    if (t === "b") return raw === "true";
    return raw;
  };

  const requiredMark = () => (block.required ? "*" : "");
  const pathKey = () => block.yamlPath.join(".");

  const canDelete = () => Boolean(block.present && block.actions.deletePath && !block.required);

  const onDelete = () => {
    if (!block.actions.deletePath) return;
    onAction(block.actions.deletePath({ pruneEmptyParents: true }), "Remove " + pathKey());
  };

  const onCreate = () => {
    const schemaType = typeof (block.schemaNode?.expanded as any)?.type === "string" ? String((block.schemaNode.expanded as any).type) : "unknown";

    if (block.kind === "object" || block.kind === "map") {
      if (!block.actions.ensureMap) return;
      onAction(block.actions.ensureMap({ createMissing: true }), "Create " + pathKey());
      return;
    }
    if (block.kind === "array") {
      if (!block.actions.ensureSeq) return;
      onAction(block.actions.ensureSeq({ createMissing: true }), "Create " + pathKey());
      return;
    }
    if (block.kind === "custom") {
      if ((schemaType === "array" || (block.schemaNode?.expanded as any)?.items != null) && block.actions.ensureSeq) {
        onAction(block.actions.ensureSeq({ createMissing: true }), "Create " + pathKey());
        return;
      }
      if (block.actions.ensureMap) {
        onAction(block.actions.ensureMap({ createMissing: true }), "Create " + pathKey());
        return;
      }
    }
    if (block.kind === "enum") {
      if (!block.actions.setScalar) return;
      const v = block.enum?.values?.[0];
      if (v === undefined) return;
      onAction(block.actions.setScalar(v, { createMissing: true }), "Create " + pathKey());
      return;
    }
    if (block.kind === "scalar") {
      if (!block.actions.setScalar) return;
      const t = block.scalar?.type || "unknown";
      const v: ScalarValue = t === "number" || t === "integer" ? 0 : t === "boolean" ? false : t === "null" ? null : "";
      onAction(block.actions.setScalar(v, { createMissing: true }), "Create " + pathKey());
    }
  };

  let scalarDraft = $state("");
  let enumDraft = $state("");
  let addArrayDraft = $state("");
  let addMapKeyDraft = $state("");
  let addMapScalarDraft = $state("");

  $effect(() => {
    if (block.kind === "scalar") scalarDraft = scalarToString(block.scalar?.value);
    if (block.kind === "enum") {
      const v = block.enum?.value;
      enumDraft = v === undefined ? "" : enumValueKey(v);
    }
  });

  const applyScalarDraft = () => {
    if (!block.actions.setScalar) return;
    const t = block.scalar?.type || "unknown";
    const raw = scalarDraft;

    if (!raw.trim() && !block.required) {
      if (block.actions.deletePath) onAction(block.actions.deletePath({ pruneEmptyParents: true }), "Remove " + pathKey());
      return;
    }

    if (t === "boolean") {
      const v = raw.trim().toLowerCase() === "false" ? false : true;
      onAction(block.actions.setScalar(v, { createMissing: true }), "Update " + pathKey());
      return;
    }

    if (t === "number" || t === "integer") {
      const n = Number(raw.trim());
      if (!Number.isFinite(n)) return;
      onAction(block.actions.setScalar(n, { createMissing: true }), "Update " + pathKey());
      return;
    }

    if (t === "null") {
      onAction(block.actions.setScalar(null, { createMissing: true }), "Update " + pathKey());
      return;
    }

    onAction(block.actions.setScalar(raw, { createMissing: true }), "Update " + pathKey());
  };

  const applyEnumDraft = () => {
    if (!block.actions.setScalar) return;
    if (!enumDraft) return;
    const v = parseEnumValueKey(enumDraft);
    onAction(block.actions.setScalar(v, { createMissing: true }), "Update " + pathKey());
  };

  const onAddArrayItem = () => {
    if (!block.actions.insertSeqItem) return;
    const idx = block.children.length;
    const itemsSchema = block.array?.itemsSchema?.expanded || {};
    const itemsType = typeof (itemsSchema as any).type === "string" ? String((itemsSchema as any).type) : "unknown";
    const itemsHasProps = isPlainObject((itemsSchema as any).properties);
    const itemsHasMap = isPlainObject((itemsSchema as any).additionalProperties) || isPlainObject((itemsSchema as any).patternProperties);

    if (itemsType === "object" || itemsHasProps || itemsHasMap) {
      onAction(block.actions.insertSeqItem(idx, "{}", { valueKind: "inline" }), "Insert " + pathKey() + "[" + String(idx) + "]");
      return;
    }

    const value = addArrayDraft.trim();
    if (!value) return;
    onAction(block.actions.insertSeqItem(idx, value, { valueKind: "string" }), "Insert " + pathKey() + "[" + String(idx) + "]");
    addArrayDraft = "";
  };

  const moveItem = (from: number, to: number) => {
    if (!block.actions.moveSeqItem) return;
    onAction(block.actions.moveSeqItem(from, to), "Move " + pathKey() + "[" + String(from) + "]");
  };

  const removeItem = (index: number) => {
    if (!block.actions.removeSeqItem) return;
    onAction(block.actions.removeSeqItem(index), "Remove " + pathKey() + "[" + String(index) + "]");
  };

  const onAddMapKey = () => {
    const key = addMapKeyDraft.trim();
    if (!key) return;

    const valueSchema = block.map?.valueSchema?.expanded || {};
    const t = typeof (valueSchema as any).type === "string" ? String((valueSchema as any).type) : "unknown";
    const hasProps = isPlainObject((valueSchema as any).properties);
    const hasMap = isPlainObject((valueSchema as any).additionalProperties) || isPlainObject((valueSchema as any).patternProperties);

    if (t === "object" || hasProps || hasMap) {
      onAction({ kind: "ensure_map", path: block.yamlPath.concat([key]), createMissing: true }, "Create " + pathKey() + "." + key);
      addMapKeyDraft = "";
      return;
    }

    if (t === "array") {
      onAction({ kind: "ensure_seq", path: block.yamlPath.concat([key]), createMissing: true }, "Create " + pathKey() + "." + key);
      addMapKeyDraft = "";
      return;
    }

    const raw = addMapScalarDraft.trim();
    onAction({ kind: "set", path: block.yamlPath.concat([key]), value: raw, createMissing: true }, "Create " + pathKey() + "." + key);
    addMapKeyDraft = "";
    addMapScalarDraft = "";
  };

  const onSelectUnionOption = (optionId: string) => {
    if (!block.union) return;
    const opt = block.union.options.find((o) => o.id === optionId) || null;
    if (!opt || !opt.discriminator) return;
    if (opt.discriminator.kind !== "const") return;
    onAction(
      { kind: "set", path: block.yamlPath.concat(opt.discriminator.path), value: opt.discriminator.value, createMissing: true },
      "Select " + pathKey()
    );
  };
</script>

<div class="rounded-lg border bg-white px-3 py-2" style="margin-left: {depth * 12}px">
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="truncate text-xs font-semibold text-slate-800 transition-colors hover:text-slate-900 hover:underline decoration-slate-200 underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
          title="Click to reveal in YAML"
          onclick={() => onJumpToYaml(block.yamlPath)}
        >
          {block.title}{requiredMark()}
        </button>
        {#if !block.present}
          <span class="rounded-md border bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">missing</span>
        {/if}
        <span class="truncate font-mono text-[10px] text-slate-400">{pathKey()}</span>
      </div>
      {#if block.description}
        <div class="mt-1 line-clamp-3 text-[11px] text-slate-500">{block.description}</div>
      {/if}
    </div>

    <div class="flex flex-none items-center gap-2">
      {#if !block.present}
        <Button variant="add" size="icon" aria-label={"create " + pathKey()} title={"create " + pathKey()} on:click={onCreate} />
      {/if}
      {#if canDelete()}
        <Button variant="danger" size="icon" aria-label={"remove " + pathKey()} title={"remove " + pathKey()} on:click={onDelete} />
      {/if}
    </div>
  </div>

  <div class="mt-2">
    {#if block.kind === "custom" && block.custom}
      <svelte:component this={block.custom.component as any} {...(block.custom.props || {})} />
    {:else if block.kind === "unsupported"}
      <div class="flex items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <div class="min-w-0 truncate">{block.unsupported?.reason || "unsupported"}</div>
        <Button variant="outline" size="sm" on:click={() => onJumpToYaml(block.unsupported?.rawYamlPath || block.yamlPath)}>Raw YAML</Button>
      </div>
    {:else if block.kind === "union" && block.union}
      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2 text-xs">
          <span class="text-[11px] font-medium text-slate-600">Union</span>
          <select
            class="sx-select"
            aria-label="union selector"
            value={block.union.inferredOptionId || ""}
            onchange={(e) => onSelectUnionOption((e.target as HTMLSelectElement).value)}
          >
            {#each block.union.options as opt (opt.id)}
              <option value={opt.id}>{opt.title}</option>
            {/each}
          </select>
        </div>
        {#if block.children.length}
          <div class="flex flex-col gap-2">
            {#each block.children as child (child.id)}
              <svelte:self block={child} depth={depth + 1} {onAction} {onJumpToYaml} />
            {/each}
          </div>
        {/if}
      </div>
    {:else if block.kind === "enum" && block.enum}
      <div class="flex items-center gap-2">
        <select class="sx-select" aria-label={pathKey()} bind:value={enumDraft} onchange={applyEnumDraft} disabled={block.enum.values.length <= 1}>
          {#each block.enum.values as v (enumValueKey(v))}
            <option value={enumValueKey(v)}>{String(v)}</option>
          {/each}
        </select>
      </div>
    {:else if block.kind === "scalar" && block.scalar}
      {#if block.scalar.type === "boolean"}
        <select
          class="sx-select"
          aria-label={pathKey()}
          value={(block.scalar.value as any) === false ? "false" : "true"}
          onchange={(e) => {
            if (!block.actions.setScalar) return;
            const v = (e.target as HTMLSelectElement).value === "false" ? false : true;
            onAction(block.actions.setScalar(v, { createMissing: true }), "Update " + pathKey());
          }}
        >
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      {:else}
        <input class="sx-input w-full" aria-label={pathKey()} bind:value={scalarDraft} onblur={applyScalarDraft} />
      {/if}
    {:else if block.kind === "array" && block.array}
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <div class="text-[11px] text-slate-600">
            {#if block.array.length == null}
              unknown length
            {:else}
              {block.array.length} items
            {/if}
          </div>
          <div class="flex items-center gap-2">
            {#if block.actions.insertSeqItem}
              <input class="sx-input-sm w-[180px]" placeholder="new item (string)" bind:value={addArrayDraft} />
              <Button
                variant="add"
                size="icon"
                aria-label={"add " + pathKey()}
                title={"add " + pathKey()}
                on:click={onAddArrayItem}
              />
            {/if}
          </div>
        </div>

        {#if block.children.length === 0}
          <div class="rounded-md border bg-slate-50 px-3 py-2 text-xs text-slate-600">No items</div>
        {:else}
          <div class="flex flex-col gap-2">
            {#each block.children as child, idx (child.id)}
              <div class="flex items-start gap-2">
                <div class="flex flex-col gap-1 pt-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={"move up " + child.id}
                    disabled={idx === 0}
                    on:click={() => moveItem(idx, idx - 1)}
                  >
                    ↑
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={"move down " + child.id}
                    disabled={idx === block.children.length - 1}
                    on:click={() => moveItem(idx, idx + 1)}
                  >
                    ↓
                  </Button>
                  <Button variant="danger" size="icon" aria-label={"remove " + child.id} on:click={() => removeItem(idx)}>×</Button>
                </div>
                <div class="min-w-0 flex-1">
                  <svelte:self block={child} depth={depth + 1} {onAction} {onJumpToYaml} />
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else if block.kind === "map" && block.map}
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-2">
          <div class="text-[11px] text-slate-600">{block.map.keys.length} keys</div>
          <div class="flex items-center gap-2">
            <input class="sx-input-sm w-[140px]" placeholder="new key" bind:value={addMapKeyDraft} />
            <input class="sx-input-sm w-[160px]" placeholder="value (scalar)" bind:value={addMapScalarDraft} />
            <Button
              variant="add"
              size="icon"
              aria-label={"add key " + pathKey()}
              title={"add key " + pathKey()}
              on:click={onAddMapKey}
            />
          </div>
        </div>
        {#if block.children.length}
          <div class="flex flex-col gap-2">
            {#each block.children as child (child.id)}
              <svelte:self block={child} depth={depth + 1} {onAction} {onJumpToYaml} />
            {/each}
          </div>
        {/if}
      </div>
    {:else if block.kind === "object"}
      {#if block.children.length === 0}
        <div class="rounded-md border bg-slate-50 px-3 py-2 text-xs text-slate-600">No properties</div>
      {:else}
        <div class="flex flex-col gap-2">
          {#each block.children as child (child.id)}
            <svelte:self block={child} depth={depth + 1} {onAction} {onJumpToYaml} />
          {/each}
        </div>
      {/if}
    {/if}
  </div>
</div>
