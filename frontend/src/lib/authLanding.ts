export const heroCapabilities = [
  "原件归档",
  "OCR 识别",
  "人工校对",
  "项目分类",
  "权限管理",
  "结构化导出",
] as const;

export const workflowCapabilities = [
  "原件归档",
  "OCR 识别",
  "人工校对",
  "重复检测",
  "项目分类",
  "权限管理",
  "JSON",
  "CSV",
  "XLSX",
] as const;

export const workflowSteps = [
  {
    title: "上传原件",
    description: "保存发票文件，建立可追溯的电子档案。",
  },
  {
    title: "OCR 提取",
    description: "提取票面字段与明细，进入结构化流程。",
  },
  {
    title: "人工校对",
    description: "核验识别结果、明细与重复风险。",
  },
  {
    title: "项目归档",
    description: "按项目、用户与权限组织发票数据。",
  },
  {
    title: "结构化导出",
    description: "生成 JSON、CSV 或 XLSX 交付文件。",
  },
] as const;

export function forceEngagedPanel(options: {
  busy: boolean;
  errorMessage: string | null;
  mode: "bootstrap" | "login";
}): boolean {
  return options.mode === "bootstrap" || options.busy || Boolean(options.errorMessage);
}
