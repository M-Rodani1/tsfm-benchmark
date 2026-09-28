import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { session, store, sync } from "./lib/app";
import "./styles.css";

async function boot() {
  const theme = localStorage.getItem("theme");
  if (theme === "dark" || theme === "light") document.documentElement.setAttribute("data-theme", theme);
  await store.init();
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
