import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Building2, FileText, Folder, Search, X } from "lucide-react";

import { apiGet } from "../lib/api";


type SearchInvoice = {
  id: string;
  invoice_number: string | null;
  invoice_code: string | null;
  seller_name: string | null;
  buyer_name: string | null;
  amount_with_tax: string | null;
};

type SearchProject = {
  id: string;
  name: string;
  description: string | null;
};

type SearchSupplier = {
  name: string;
  invoice_count: number;
};

type SearchResponse = {
  invoices: SearchInvoice[];
  projects: SearchProject[];
  suppliers: SearchSupplier[];
};

type SearchItem = {
  description: string;
  href: string;
  id: string;
  kind: "invoice" | "project" | "supplier";
  label: string;
};

const emptyResults: SearchResponse = { invoices: [], projects: [], suppliers: [] };

export function GlobalSearchDialog({ onClose, open }: { onClose: () => void; open: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const requestSequence = useRef(0);
  const [activeIndex, setActiveIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse>(emptyResults);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const items = useMemo(() => flattenResults(results), [results]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const handleWindowKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleWindowKeyDown);
    return () => window.removeEventListener("keydown", handleWindowKeyDown);
  }, [onClose, open]);

  useEffect(() => {
    if (!open) {
      requestSequence.current += 1;
      setQuery("");
      setResults(emptyResults);
      setStatus("idle");
      setMessage("");
      return;
    }

    const normalized = query.trim();
    if (normalized.length < 2) {
      requestSequence.current += 1;
      setResults(emptyResults);
      setStatus("idle");
      setMessage("");
      return;
    }

    const sequence = ++requestSequence.current;
    setStatus("loading");
    setMessage("");
    const timer = window.setTimeout(() => {
      apiGet<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(normalized)}&limit=6`)
        .then((data) => {
          if (requestSequence.current !== sequence) return;
          setResults(data);
          setActiveIndex(0);
          setStatus("ready");
        })
        .catch(() => {
          if (requestSequence.current !== sequence) return;
          setResults(emptyResults);
          setStatus("error");
          setMessage("暂时无法完成搜索，请稍后重试。");
        });
    }, 200);
    return () => window.clearTimeout(timer);
  }, [open, query]);

  if (!open) return null;

  function navigate(item: SearchItem) {
    window.location.hash = item.href;
    onClose();
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!items.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % items.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + items.length) % items.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      navigate(items[activeIndex] ?? items[0]);
    }
  }

  return (
    <div className="global-search-backdrop" onMouseDown={(event) => {
      if (event.currentTarget === event.target) onClose();
    }}>
      <section aria-label="全局搜索" aria-modal="true" className="global-search-dialog" role="dialog">
        <div className="global-search-input-row">
          <Search aria-hidden="true" size={20} />
          <input
            aria-label="全局搜索"
            autoComplete="off"
            onChange={(event) => setQuery(event.currentTarget.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="搜索发票、项目或供应商"
            ref={inputRef}
            role="searchbox"
            type="search"
            value={query}
          />
          <button aria-label="关闭全局搜索" className="icon-button" onClick={onClose} type="button">
            <X aria-hidden="true" size={19} />
          </button>
        </div>

        <div className="global-search-results" aria-live="polite">
          {status === "idle" ? <p className="global-search-state">输入至少两个字符开始搜索</p> : null}
          {status === "loading" ? <p className="global-search-state">正在搜索...</p> : null}
          {status === "error" ? <p className="global-search-state error" role="alert">{message}</p> : null}
          {status === "ready" && !items.length ? <p className="global-search-state">没有找到匹配结果</p> : null}
          {status === "ready" && items.length ? (
            <SearchGroups
              activeIndex={activeIndex}
              items={items}
              onActivate={setActiveIndex}
              onSelect={navigate}
            />
          ) : null}
        </div>
      </section>
    </div>
  );
}

function SearchGroups({
  activeIndex,
  items,
  onActivate,
  onSelect,
}: {
  activeIndex: number;
  items: SearchItem[];
  onActivate: (index: number) => void;
  onSelect: (item: SearchItem) => void;
}) {
  const groups = [
    { icon: FileText, kind: "invoice" as const, label: "发票" },
    { icon: Folder, kind: "project" as const, label: "项目" },
    { icon: Building2, kind: "supplier" as const, label: "供应商" },
  ];

  return groups.map((group) => {
    const groupItems = items.filter((item) => item.kind === group.kind);
    if (!groupItems.length) return null;
    const Icon = group.icon;
    return (
      <section className="global-search-group" key={group.kind}>
        <h2><Icon aria-hidden="true" size={15} />{group.label}</h2>
        <div>
          {groupItems.map((item) => {
            const index = items.indexOf(item);
            return (
              <button
                aria-selected={index === activeIndex}
                className={index === activeIndex ? "active" : ""}
                key={item.id}
                onClick={() => onSelect(item)}
                onMouseEnter={() => onActivate(index)}
                role="option"
                type="button"
              >
                <span><strong>{item.label}</strong><small>{item.description}</small></span>
              </button>
            );
          })}
        </div>
      </section>
    );
  });
}

function flattenResults(results: SearchResponse): SearchItem[] {
  return [
    ...results.invoices.map((invoice) => ({
      description: [invoice.seller_name, invoice.buyer_name, invoice.amount_with_tax ? `¥${invoice.amount_with_tax}` : null].filter(Boolean).join(" · "),
      href: `#/invoices/${invoice.id}`,
      id: `invoice-${invoice.id}`,
      kind: "invoice" as const,
      label: invoice.invoice_number || invoice.invoice_code || "未编号发票",
    })),
    ...results.projects.map((project) => ({
      description: project.description || "查看项目发票",
      href: `#/invoices?project_id=${encodeURIComponent(project.id)}`,
      id: `project-${project.id}`,
      kind: "project" as const,
      label: project.name,
    })),
    ...results.suppliers.map((supplier) => ({
      description: `${supplier.invoice_count} 张相关发票`,
      href: `#/invoices?seller_name=${encodeURIComponent(supplier.name)}`,
      id: `supplier-${supplier.name}`,
      kind: "supplier" as const,
      label: supplier.name,
    })),
  ];
}
