import type { PropsWithChildren } from "react";
import { Bell, Search, Upload } from "lucide-react";

import { appRoutes, type AppRoute } from "../app/router";
import { useAuth } from "../auth/AuthContext";
import { visibleNavigationIds } from "../lib/permissions";
import { OcrQuotaStatus } from "./OcrQuotaStatus";
import { UserMenu } from "./UserMenu";

export function AppShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: AppRoute }>) {
  const auth = useAuth();
  const visibleRoutes = appRoutes.filter((route) =>
    auth.user ? visibleNavigationIds(auth.user.role).includes(route.id) : false,
  );

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <a className="brand" href="#/" aria-label="Invoice OCR 总览">
          <span>
            <strong>Invoice OCR</strong>
            <small>发票识别与归档</small>
          </span>
        </a>

        <nav className="nav-list">
          <span className="nav-list-caption">工作区 / 01</span>
          {visibleRoutes.map((route, index) => (
            <a className={route.id === activeRoute.id ? "active" : ""} href={route.path} key={route.id}>
              <i className="shell-nav-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</i>
              <span>{route.label}</span>
              {route.badge ? <em>{route.badge}</em> : null}
            </a>
          ))}
        </nav>

        <OcrQuotaStatus compact />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="topbar-breadcrumb">
            <span>发票管理</span>
            <i aria-hidden="true">/</i>
            <strong>{activeRoute.label}</strong>
          </div>
          <button className="shell-command-search" type="button">
            <Search aria-hidden="true" size={14} />
            <span>搜索发票、项目或供应商</span>
            <kbd>⌘ K</kbd>
          </button>
          <div className="topbar-actions" aria-label="系统状态">
            <button className="topbar-icon-button" aria-label="通知" type="button"><Bell aria-hidden="true" size={15} /></button>
            <span className="shell-local-state"><i aria-hidden="true" />本地运行</span>
            <a className="button primary shell-upload-command" href="#/upload"><Upload aria-hidden="true" size={14} />上传发票</a>
            {auth.user ? (
              <UserMenu user={auth.user} onChangePassword={auth.changePassword} onLogout={auth.logout} />
            ) : null}
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}
