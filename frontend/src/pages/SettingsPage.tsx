import { OcrProviderSettings } from "../components/OcrProviderSettings";
import { OcrQuotaStatus } from "../components/OcrQuotaStatus";

export function SettingsPage() {
  return (
    <div className="page-stack">
      <section className="surface-panel settings-intro">
        <div>
          <span className="section-label">系统设置</span>
          <h2>OCR 运营商、凭据与额度提醒</h2>
          <p>凭据只在提交时发送到后端加密保存；页面仅显示配置状态和凭据指纹，不回显 SecretId 或 SecretKey。</p>
        </div>
        <OcrQuotaStatus compact />
      </section>
      <OcrProviderSettings />
    </div>
  );
}
