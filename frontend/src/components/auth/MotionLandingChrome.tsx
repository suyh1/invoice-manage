import { type CSSProperties, type ReactNode } from "react";
import { CircleCheckBig, FileOutput, FolderTree, ScanLine, Upload } from "lucide-react";

import { heroCapabilities, workflowCapabilities, workflowSteps } from "../../lib/authLanding";

type MotionLandingChromeProps = {
  bootstrap?: boolean;
  children: ReactNode;
};

const workflowIcons = [Upload, ScanLine, CircleCheckBig, FolderTree, FileOutput] as const;

export function MotionLandingChrome({ bootstrap = false, children }: MotionLandingChromeProps) {
  return (
    <main className={`motion-auth-page${bootstrap ? " is-bootstrap" : ""}`}>
      <MotionNavbar />

      <section className="motion-auth-hero" aria-labelledby="auth-product-title">
        <div className="motion-auth-background" aria-hidden="true" />
        <PulseLines />

        <div className="motion-auth-hero-content">
          <TextMarquee className="motion-auth-ticker" items={heroCapabilities} />

          <header className="motion-auth-copy">
            <h1 id="auth-product-title">
              Every invoice, <em>traceable.</em>
            </h1>
            <p>从上传、识别、校对到项目导出，让每一张发票都有清晰去向。</p>
          </header>

          {children}
        </div>

        <div className="motion-auth-progressive-blur" aria-hidden="true" />
      </section>

      <CapabilityBand />
      <WorkflowIndex />
      <LandingFooter />
    </main>
  );
}

function MotionNavbar() {
  return (
    <header className="motion-auth-navbar">
      <a className="motion-auth-brand" href="#top" aria-label="Invoice OCR 发票识别与归档">
        <span>Invoice OCR</span>
        <small>发票识别与归档</small>
      </a>
    </header>
  );
}

function PulseLines() {
  const desktopLines = Array.from({ length: 20 }, (_, index) => ({
    delay: `${index * 0.25}s`,
    size: `${60 + index * 10}px`,
  }));
  const mobileLines = Array.from({ length: 40 }, (_, index) => ({
    delay: `${index * 0.125}s`,
    size: `${56 + index * 9}px`,
  }));

  return (
    <div className="motion-auth-lines" aria-hidden="true">
      <div className="motion-auth-lines-side motion-auth-lines-left">
        {desktopLines.map((line, index) => (
          <span
            className="motion-line-left"
            key={`left-${index}`}
            style={{ "--line-delay": line.delay, "--line-size": line.size } as CSSProperties}
          />
        ))}
      </div>
      <div className="motion-auth-lines-side motion-auth-lines-right">
        {desktopLines.map((line, index) => (
          <span
            className="motion-line-right"
            key={`right-${index}`}
            style={{ "--line-delay": line.delay, "--line-size": line.size } as CSSProperties}
          />
        ))}
      </div>
      <div className="motion-auth-lines-top">
        {mobileLines.map((line, index) => (
          <span
            className="motion-line-top"
            key={`top-${index}`}
            style={{ "--line-delay": line.delay, "--line-size": line.size } as CSSProperties}
          />
        ))}
      </div>
    </div>
  );
}

function TextMarquee({ className, items }: { className?: string; items: readonly string[] }) {
  return (
    <div className={className} aria-hidden="true">
      <div className="motion-auth-marquee-track">
        {Array.from({ length: 4 }, (_, groupIndex) => (
          <div className="motion-auth-marquee-group" key={groupIndex}>
            {items.map((item) => (
              <span key={`${groupIndex}-${item}`}>{item}</span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function CapabilityBand() {
  return (
    <section className="motion-auth-capability-band" aria-label="系统能力">
      <TextMarquee className="motion-auth-capability-marquee" items={workflowCapabilities} />
    </section>
  );
}

function WorkflowIndex() {
  return (
    <section className="motion-auth-workflow" id="workflow" aria-labelledby="workflow-title">
      <h2 id="workflow-title">从原件到可交付数据</h2>
      <div className="motion-auth-workflow-grid">
        {workflowSteps.map((step, index) => {
          const Icon = workflowIcons[index];
          return (
            <article key={step.title}>
              <div className="motion-auth-workflow-number">{String(index + 1).padStart(2, "0")}</div>
              <Icon aria-hidden="true" size={28} strokeWidth={1.7} />
              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="motion-auth-footer" id="private-deployment">
      <span>Invoice OCR</span>
      <span>面向内部财务流程的私有化发票管理系统</span>
    </footer>
  );
}
