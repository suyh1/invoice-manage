import { OcrProviderSettings } from '../components/OcrProviderSettings';
import { OcrQuotaStatus } from '../components/OcrQuotaStatus';

export function SettingsPage() {
  return (
    <div className="page-stack settings-editorial">
      <section className="surface-panel settings-intro editorial-page-heading">
        <div>
          <span className="section-label">SYSTEM CONTROL / 系统设置</span>
          <h2>OCR 运营商、凭据与额度提醒</h2>
          <p>凭据只在提交时发送到后端加密保存；页面仅显示配置状态和凭据指纹。</p>
        </div>
        <OcrQuotaStatus compact />
      </section>
      <OcrProviderSettings />
    </div>
  );
}
