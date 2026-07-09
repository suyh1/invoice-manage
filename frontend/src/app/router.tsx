import { useEffect, useMemo, useState } from "react";

import { DashboardPage } from "../pages/DashboardPage";
import { SettingsPage } from "../pages/SettingsPage";
import { UploadPage } from "../pages/UploadPage";

export type AppRouteId = "dashboard" | "invoices" | "upload" | "review" | "exports" | "settings";

export type AppRoute = {
  id: AppRouteId;
  label: string;
  path: string;
  badge?: string;
};

export const appRoutes: AppRoute[] = [
  { id: "dashboard", label: "总览", path: "#/" },
  { id: "invoices", label: "发票库", path: "#/invoices" },
  { id: "upload", label: "上传识别", path: "#/upload" },
  { id: "review", label: "待校对", path: "#/review", badge: "0" },
  { id: "exports", label: "导出记录", path: "#/exports" },
  { id: "settings", label: "设置", path: "#/settings" },
];

export function useHashRoute() {
  const [hash, setHash] = useState(() => window.location.hash || "#/");

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return useMemo(() => {
    return appRoutes.find((route) => route.path === hash) ?? appRoutes[0];
  }, [hash]);
}

export function renderRoute(route: AppRoute) {
  if (route.id === "settings") {
    return <SettingsPage />;
  }
  if (route.id === "dashboard") {
    return <DashboardPage />;
  }
  if (route.id === "upload") {
    return <UploadPage />;
  }
  return <PlaceholderPage route={route} />;
}

function PlaceholderPage({ route }: { route: AppRoute }) {
  const copy: Record<AppRouteId, string> = {
    dashboard: "",
    invoices: "发票筛选、批量操作和详情校对将在后续任务接入。",
    upload: "批量上传、预校验和 OCR 队列将在上传工作流任务中接入。",
    review: "字段缺失、重复疑似和低置信度聚合将在校对任务中接入。",
    exports: "导出任务列表和下载状态将在导出页面任务中接入。",
    settings: "",
  };

  return (
    <section className="surface-panel empty-panel">
      <div>
        <p className="section-label">{route.label}</p>
        <h1>{route.label}</h1>
        <p>{copy[route.id]}</p>
      </div>
    </section>
  );
}
