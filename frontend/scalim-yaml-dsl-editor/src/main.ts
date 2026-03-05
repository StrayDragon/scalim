import "./app.css";
import { mount } from "svelte";
import Root from "$app/Root.svelte";

mount(Root, {
  target: document.getElementById("app") as HTMLElement
});

