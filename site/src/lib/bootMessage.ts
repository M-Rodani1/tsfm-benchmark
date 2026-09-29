// A plain message in the page before (or instead of) the React app, so a failure while
// starting never leaves a blank page. Text only (no HTML is interpreted).
export function bootMessage(title: string, detail = "") {
  const root = document.getElementById("root");
  if (!root) return;
  root.replaceChildren();
  const box = document.createElement("div");
  box.setAttribute("role", "alert");
  box.setAttribute("data-testid", "boot-message");
  box.style.cssText = "max-width:640px;margin:48px auto;padding:16px 20px;border-radius:10px;font:16px/1.5 system-ui,sans-serif;" +
    "background:#fff4dc;color:#5c4300";
  const h = document.createElement("strong");
  h.textContent = title;
  box.append(h);
  if (detail) {
    const p = document.createElement("p");
    p.textContent = detail;
    p.style.margin = "8px 0 0";
    box.append(p);
  }
  root.append(box);
}
