import type { PropsWithChildren } from "react";

import { appRoutes, type AppRoute } from "../app/router";
import { OcrQuotaStatus } from "./OcrQuotaStatus";

export function AppShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: AppRoute }>) {
  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <a className="brand" href="#/" aria-label="Invoice OCR 总览">
          <span className="brand-mark" aria-hidden="true">
            IO
          </span>
          <span>
            <strong>Invoice OCR</strong>
            <small>发票识别工作台</small>
          </span>
        </a>

        <nav className="nav-list">
          {appRoutes.map((route) => (
            <a className={route.id === activeRoute.id ? "active" : ""} href={route.path} key={route.id}>
              <span>{route.label}</span>
              {route.badge ? <em>{route.badge}</em> : null}
            </a>
          ))}
        </nav>

        <OcrQuotaStatus compact />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="section-label">当前模块</span>
            <h1>{activeRoute.label}</h1>
          </div>
          <div className="topbar-actions" aria-label="系统状态">
            <span className="status-token success">本地部署</span>
            <span className="status-token neutral">Mock OCR 可用</span>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}
