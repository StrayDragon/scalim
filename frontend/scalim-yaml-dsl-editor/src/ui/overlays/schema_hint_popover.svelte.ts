export const schemaHintPopover = $state({
  open: false,
  pinned: false,
  text: "",
  label: "Schema 提示",
  anchorEl: null as HTMLElement | null
});

export const openSchemaHintPopover = (opts: { anchorEl: HTMLElement | null; text: string; label: string; pinned?: boolean }) => {
  if (!opts.text) return;
  schemaHintPopover.open = true;
  schemaHintPopover.pinned = Boolean(opts.pinned);
  schemaHintPopover.text = opts.text;
  schemaHintPopover.label = opts.label || "Schema 提示";
  schemaHintPopover.anchorEl = opts.anchorEl;
};

export const updateSchemaHintPopover = (opts: { text?: string; label?: string }) => {
  if (!schemaHintPopover.open) return;
  if (typeof opts.text === "string") schemaHintPopover.text = opts.text;
  if (typeof opts.label === "string") schemaHintPopover.label = opts.label;
};

export const closeSchemaHintPopover = () => {
  schemaHintPopover.open = false;
  schemaHintPopover.pinned = false;
  schemaHintPopover.text = "";
  schemaHintPopover.label = "Schema 提示";
  schemaHintPopover.anchorEl = null;
};

let closeTimer: number | null = null;

export const cancelCloseSchemaHintPopover = () => {
  if (closeTimer == null) return;
  window.clearTimeout(closeTimer);
  closeTimer = null;
};

export const scheduleCloseSchemaHintPopover = (delayMs = 180) => {
  if (!schemaHintPopover.open) return;
  if (schemaHintPopover.pinned) return;
  cancelCloseSchemaHintPopover();
  closeTimer = window.setTimeout(() => {
    closeTimer = null;
    closeSchemaHintPopover();
  }, delayMs);
};
