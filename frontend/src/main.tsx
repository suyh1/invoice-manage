import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles.css";

const navigationItems = ["总览", "发票库", "上传识别", "待校对", "导出记录", "设置"];

function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            IO
          </span>
          <div>
            <strong>Invoice OCR</strong>
            <span>发票识别工作台</span>
          </div>
        </div>
        <nav>
          {navigationItems.map((item, index) => (
            <button className={index === 0 ? "active" : ""} key={item} type="button">
              {item}
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header className="page-header">
          <div>
            <p>系统总览</p>
            <h1>发票集中存储与 OCR 识别</h1>
          </div>
          <span className="status-pill">Mock OCR ready</span>
        </header>
        <section className="dashboard-grid" aria-label="关键指标">
          <article>
            <span>待校对</span>
            <strong>0</strong>
          </article>
          <article>
            <span>识别失败</span>
            <strong>0</strong>
          </article>
          <article>
            <span>队列积压</span>
            <strong>0</strong>
          </article>
          <article>
            <span>额度提醒</span>
            <strong>未配置</strong>
          </article>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

