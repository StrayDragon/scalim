import { Collapsible as CollapsiblePrimitive } from "bits-ui";
import Content from "./content.svelte";
import Trigger from "./trigger.svelte";

const Root = CollapsiblePrimitive.Root;

export const Collapsible = {
  Root,
  Trigger,
  Content
};

export { Root, Trigger, Content };
