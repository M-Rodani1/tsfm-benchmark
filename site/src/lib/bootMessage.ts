// A plain message in the page before (or instead of) the React app, so a failure while
// starting never leaves a blank page. Text only (no HTML is interpreted).
export function bootMessage(title: string, detail = "") {
  const root = document.getElementById("root");
  if (!root) return;
  root.replaceChildren();
  const box = document.createElement("div");
  box.setAttribute("role", "alert");
  box.setAttribute("data-testid", "boot-message");
  // the error state of the design (site/DESIGN.md), inline because the stylesheet may not have loaded
  box.style.cssText = "max-width:640px;margin:48px auto;padding:14px 18px;border-radius:6px;font:15px/1.5 system-ui,sans-serif;" +
    "background:#ffffff;color:#1c2330;border:1px solid #dde1e7;border-left:3px solid #b42318";
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
