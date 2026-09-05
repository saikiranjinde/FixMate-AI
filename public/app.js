const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

$("#year").textContent = new Date().getFullYear();

$$("[data-scroll]").forEach(btn => {
  btn.addEventListener("click", () => $(btn.dataset.scroll)?.scrollIntoView({behavior:"smooth"}));
});

function openDialog(id){
  const el = document.getElementById(id);
  if (el && typeof el.showModal === "function") el.showModal();
  else if (el) el.setAttribute("open", "");
}
function closeDialog(el){
  if (el?.close) el.close();
  else el?.removeAttribute("open");
}

$$("[data-open]").forEach(btn => btn.addEventListener("click", () => openDialog(btn.dataset.open)));
$$("[data-close]").forEach(btn => btn.addEventListener("click", () => closeDialog(btn.closest("dialog"))));

$$("dialog").forEach(dialog => {
  dialog.addEventListener("click", e => {
    if (e.target === dialog) closeDialog(dialog);
  });
});

$$(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const root = tab.closest(".modal");
    $$(".tab", root).forEach(t => t.classList.remove("active"));
    $$(".tab-panel", root).forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    $(`[data-panel="${tab.dataset.tab}"]`, root)?.classList.add("active");
  });
});

let toastTimer;
$$("[data-download]").forEach(link => {
  link.addEventListener("click", () => {
    const toast = $("#downloadToast");
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 7000);
  });
});

$("[data-dismiss-toast]").addEventListener("click", () => $("#downloadToast").classList.remove("show"));

// Small loading state on download buttons. The download itself remains native browser behavior.
$$("[data-download]").forEach(link => {
  link.addEventListener("click", () => {
    const original = link.innerHTML;
    link.innerHTML = '<span class="toast-loader" style="width:16px;height:16px;border-width:2px"></span><span>Starting download…</span>';
    link.style.pointerEvents = "none";
    setTimeout(() => {
      link.innerHTML = original;
      link.style.pointerEvents = "";
    }, 1800);
  });
});
