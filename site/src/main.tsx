import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { session, store, sync } from "./lib/app";
import { bootMessage } from "./lib/bootMessage";
import "./styles.css";

async function boot() {
  try {
    const theme = localStorage.getItem("theme");
    if (theme === "dark" || theme === "light") document.documentElement.setAttribute("data-theme", theme);
  } catch {
    /* storage blocked: default theme */
  }
  try {
    await store.init();
  } catch (e) {
    console.error("could not open the local store", e);
    bootMessage("The site could not open its storage in this browser, so it cannot start.",
      `${e instanceof Error ? e.message : String(e)} — Try reloading. If this keeps happening, your progress is still in this browser; ` +
      "open the site in another browser meanwhile, or clear this site's data (after an export, if you can) to start again.");
    return;
  }
  session.start();
  void sync.start();
  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("service worker not registered", e));
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void boot();
