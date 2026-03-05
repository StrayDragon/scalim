import { Dialog as DialogPrimitive } from "bits-ui";
import Content from "./content.svelte";
import Overlay from "./overlay.svelte";
import Title from "./title.svelte";
import Description from "./description.svelte";
import Header from "./header.svelte";
import Footer from "./footer.svelte";
import Close from "./close.svelte";

const Root = DialogPrimitive.Root;
const Trigger = DialogPrimitive.Trigger;
const Portal = DialogPrimitive.Portal;

export const Dialog = {
  Root,
  Trigger,
  Portal,
  Overlay,
  Content,
  Title,
  Description,
  Header,
  Footer,
  Close
};

export { Root, Trigger, Portal, Overlay, Content, Title, Description, Header, Footer, Close };
