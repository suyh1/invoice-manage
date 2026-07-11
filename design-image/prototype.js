const params = new URLSearchParams(window.location.search);
const requestedView = params.get("view");
const view = ["dashboard", "library", "review"].includes(requestedView) ? requestedView : "dashboard";
const labels = { dashboard: "工作总览", library: "发票库", review: "人工校对" };

document.documentElement.dataset.view = view;
document.querySelectorAll("[data-screen]").forEach((screen) => {
  screen.hidden = screen.dataset.screen !== view;
});
document.querySelectorAll("[data-nav], [data-view-link]").forEach((link) => {
  const target = link.dataset.nav || link.dataset.viewLink;
  link.classList.toggle("active", target === view);
});
document.getElementById("breadcrumb-current").textContent = labels[view];

if (view === "review") document.querySelector(".app").classList.add("review-mode");
