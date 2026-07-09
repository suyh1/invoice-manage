# 腾讯云 OCR 官方约束调研

调研日期：2026-07-09

## 官方来源

- 腾讯云文字识别 `VatInvoiceOCR` 文档：https://cloud.tencent.com/document/product/866/36210
- 腾讯云 OCR API 总览：https://cloud.tencent.com/document/api/866/33515
- 腾讯云 `VatInvoiceVerifyNew` 文档：https://cloud.tencent.com/document/product/866/73674

## `VatInvoiceOCR` 关键事实

- 接口请求域名：`ocr.tencentcloudapi.com`
- Action：`VatInvoiceOCR`
- Version：`2018-11-19`
- Region：可选。实现中默认 `ap-guangzhou`，允许运维覆盖。
- 默认接口请求频率限制：`10 次/秒`
- 支持文件格式：PNG、JPG、JPEG、PDF
- 不支持文件格式：GIF
- 输入参数支持 `ImageBase64` 或 `ImageUrl`，两者都传时使用 `ImageUrl`
- 本项目 MVP 默认走本地文件 `ImageBase64`，不默认开放远程 URL 识别
- Base64 编码后文件大小不得超过 10MB
- 远程文件下载时间不得超过 3 秒
- 图片像素范围：20-10000px
- PDF 识别需传 `IsPdf=true`
- `PdfPageNumber` 仅用于 PDF 单页识别，默认第 1 页

## `VatInvoiceOCR` 输出

必须保存以下字段：

- `VatInvoiceInfos`：识别出的发票字段数组
- `Items`：发票明细项数组
- `PdfPageSize`：PDF 总页数，非 PDF 默认 0
- `Angle`：图片角度
- `RequestId`：腾讯云请求 ID，用于排障

实现必须同时保存：

- 腾讯云完整原始响应 JSON
- 系统归一化后的发票主表字段
- 系统归一化后的发票明细字段

## 常见错误类别

实现中需映射为系统内部错误码：

- 文件下载失败
- 图片内容为空
- 图片模糊
- 图片解码失败
- 图片中未检测到文本
- 图片尺寸过大
- OCR 识别失败
- 未知错误
- 服务未开通
- 参数值错误
- 文件内容太大
- 账号已欠费
- 账号资源包耗尽
- 计费状态异常

## API 总览补充

票据单据识别相关接口包含：

- `RecognizeGeneralInvoice`：通用票据识别高级版
- `VatInvoiceVerifyNew`：增值税发票核验新版
- `VatInvoiceOCR`：增值税发票识别
- `VerifyOfdVatInvoiceOCR`：OFD 发票识别
- `BankSlipOCR`：银行回单识别
- `RecognizeMedicalInvoiceOCR`：医疗票据识别

腾讯云文档说明 API 频率限制维度为 `API + 接入地域 + 子账号`。

## 二期可选：`VatInvoiceVerifyNew`

`VatInvoiceVerifyNew` 可用于增值税发票准确性核验。

- Endpoint：`ocr.tencentcloudapi.com`
- Action：`VatInvoiceVerifyNew`
- Version：`2018-11-19`
- 默认接口请求频率限制：`20 次/秒`
- 用途：通过发票号码、日期、金额、校验码等关键字段查验发票真实性

当前项目 MVP 不把发票真伪查验作为必做范围。设计保留二期 `VerificationJob` 扩展点。

