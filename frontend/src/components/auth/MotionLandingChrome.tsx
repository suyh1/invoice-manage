import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";
import {
  ChevronUp,
  CircleCheckBig,
  FileOutput,
  FolderTree,
  ScanLine,
  Upload,
} from "lucide-react";

import { heroCapabilities, workflowCapabilities, workflowSteps } from "../../lib/authLanding";

type MotionLandingChromeProps = {
  bootstrap?: boolean;
  children: ReactNode;
  onLoginRequest?: () => void;
};

const workflowIcons = [Upload, ScanLine, CircleCheckBig, FolderTree, FileOutput] as const;

const drawerLinks = [
  { href: "#auth-panel", label: "登录系统", target: "login" },
  { href: "#workflow", label: "原件归档与 OCR" },
  { href: "#workflow", label: "人工校对" },
  { href: "#workflow", label: "项目与权限" },
  { href: "#private-deployment", label: "私有部署" },
] as const;

export function MotionLandingChrome({ bootstrap = false, children, onLoginRequest }: MotionLandingChromeProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  return (
    <main className={`motion-auth-page${bootstrap ? " is-bootstrap" : ""}`}>
      <MotionNavbar
        buttonRef={menuButtonRef}
        menuOpen={menuOpen}
        onMenuToggle={() => setMenuOpen((open) => !open)}
      />
      <FullscreenMenu
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        onLoginRequest={onLoginRequest}
        triggerRef={menuButtonRef}
      />

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

function MotionNavbar({
  buttonRef,
  menuOpen,
  onMenuToggle,
}: {
  buttonRef: RefObject<HTMLButtonElement | null>;
  menuOpen: boolean;
  onMenuToggle: () => void;
}) {
  return (
    <header className="motion-auth-navbar">
      <a className="motion-auth-brand" href="#top" aria-label="Invoice OCR 发票识别与归档">
        <span>Invoice OCR</span>
        <small>发票识别与归档</small>
      </a>
      <button
        aria-expanded={menuOpen}
        aria-haspopup="dialog"
        aria-label="Menu"
        className="motion-auth-menu-button"
        onClick={onMenuToggle}
        ref={buttonRef}
        type="button"
      >
        <span>Menu</span>
        <ChevronUp aria-hidden="true" size={16} />
      </button>
    </header>
  );
}

function FullscreenMenu({
  open,
  onClose,
  onLoginRequest,
  triggerRef,
}: {
  open: boolean;
  onClose: () => void;
  onLoginRequest?: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusableElements = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );

    focusableElements()[0]?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        triggerRef.current?.focus();
        onClose();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusable = focusableElements();
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) {
        event.preventDefault();
        return;
      }

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, open, triggerRef]);

  if (!open) {
    return null;
  }

  return (
    <div
      aria-label="首页导航"
      aria-modal="true"
      className="motion-auth-menu"
      ref={dialogRef}
      role="dialog"
    >
      <nav aria-label="落地页导航">
        {drawerLinks.map((link) => (
          <a
            href={link.href}
            key={link.label}
            onClick={(event) => {
              if ("target" in link && link.target === "login") {
                event.preventDefault();
                triggerRef.current?.focus();
                onClose();
                onLoginRequest?.();
                return;
              }
              triggerRef.current?.focus();
              onClose();
            }}
          >
            {link.label}
          </a>
        ))}
      </nav>
      <footer>
        <span>Invoice OCR</span>
        <span>发票识别、校对与项目归档</span>
      </footer>
    </div>
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
      <p>围绕企业财务流程构建</p>
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
