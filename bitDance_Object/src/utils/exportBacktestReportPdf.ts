import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

function escapeHtml(text: string) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function markdownToHtml(md: string): string {
  try {
    const out = marked.parse(md, { async: false })
    return typeof out === 'string' ? out : String(out)
  } catch {
    return `<p>${escapeHtml(md)}</p>`
  }
}

function formatDisplayTime(ts: number): string {
  try {
    return new Date(ts).toLocaleString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return String(ts)
  }
}

function pdfFilename(createdAt: number): string {
  const d = new Date(createdAt)
  const p = (n: number) => String(n).padStart(2, '0')
  return `backtest-report-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.pdf`
}

const PDF_STYLES = `
  .bq-pdf-root {
    box-sizing: border-box;
    width: 794px;
    max-width: 794px;
    padding: 40px 48px;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 12px;
    line-height: 1.65;
    color: #1a1a1a;
    background: #fff;
  }
  .bq-pdf-head {
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid #7f5731;
  }
  .bq-pdf-brand {
    margin: 0 0 0.25rem;
    font-size: 18px;
    font-weight: 700;
    color: #5c3d1e;
  }
  .bq-pdf-meta {
    margin: 0;
    font-size: 11px;
    color: #666;
  }
  .bq-pdf-body h1, .bq-pdf-body h2, .bq-pdf-body h3 {
    color: #1a1a1a;
    margin: 0.85rem 0 0.45rem;
    font-weight: 650;
    page-break-after: avoid;
  }
  .bq-pdf-body h1 { font-size: 20px; }
  .bq-pdf-body h2 { font-size: 16px; }
  .bq-pdf-body h3 { font-size: 14px; }
  .bq-pdf-body p { margin: 0.45rem 0; }
  .bq-pdf-body ul, .bq-pdf-body ol {
    margin: 0.45rem 0;
    padding-left: 1.25rem;
  }
  .bq-pdf-body blockquote {
    margin: 0.5rem 0;
    padding: 0.35rem 0.65rem;
    border-left: 3px solid #b3874f;
    background: #f8f4ee;
    color: #333;
  }
  .bq-pdf-body code {
    font-family: ui-monospace, Consolas, monospace;
    font-size: 0.9em;
    background: #f0f0f0;
    border-radius: 3px;
    padding: 0.1rem 0.3rem;
  }
  .bq-pdf-body pre {
    margin: 0.5rem 0;
    padding: 0.55rem 0.65rem;
    border-radius: 4px;
    background: #f4f4f4;
    overflow-x: auto;
    page-break-inside: avoid;
  }
  .bq-pdf-body pre code { background: transparent; padding: 0; }
  .bq-pdf-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.55rem 0;
    font-size: 11px;
    page-break-inside: avoid;
  }
  .bq-pdf-body th, .bq-pdf-body td {
    border: 1px solid #ccc;
    padding: 0.35rem 0.45rem;
    text-align: left;
  }
  .bq-pdf-body th { background: #f0e6d8; font-weight: 600; }
  .bq-pdf-body img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.5rem 0;
    page-break-inside: avoid;
  }
  .bq-pdf-body hr {
    margin: 0.75rem 0;
    border: none;
    border-top: 1px solid #ddd;
  }
  .bq-pdf-body a { color: #2563eb; }
`

async function waitForImages(root: HTMLElement) {
  const images = root.querySelectorAll('img')
  await Promise.all(
    Array.from(images).map(
      (img) =>
        new Promise<void>((resolve) => {
          if (img.complete) {
            resolve()
            return
          }
          img.onload = () => resolve()
          img.onerror = () => resolve()
        }),
    ),
  )
}

export async function exportBacktestReportToPdf(body: string, createdAt: number): Promise<void> {
  const shell = document.createElement('div')
  shell.style.cssText = 'position:fixed;left:-10000px;top:0;z-index:-1;pointer-events:none;'

  const generatedAt = formatDisplayTime(createdAt)
  shell.innerHTML = `
    <style>${PDF_STYLES}</style>
    <div class="bq-pdf-root">
      <header class="bq-pdf-head">
        <p class="bq-pdf-brand">bitDance · 回测报告</p>
        <p class="bq-pdf-meta">生成时间：${escapeHtml(generatedAt)}</p>
      </header>
      <article class="bq-pdf-body">${markdownToHtml(body)}</article>
    </div>
  `

  document.body.appendChild(shell)
  const root = shell.querySelector('.bq-pdf-root') as HTMLElement | null
  if (!root) {
    document.body.removeChild(shell)
    throw new Error('PDF root element missing')
  }

  try {
    await waitForImages(root)
    const { default: html2pdf } = await import('html2pdf.js')
    await html2pdf()
      .set({
        margin: [12, 12, 14, 12],
        filename: pdfFilename(createdAt),
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      })
      .from(root)
      .save()
  } finally {
    document.body.removeChild(shell)
  }
}
