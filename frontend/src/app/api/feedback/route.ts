import { NextResponse } from "next/server";
import https from "node:https";

const DEFAULT_FROM = process.env.CONTACT_FROM || "BILUN Feedback <contact@bilun.tech>";
const DEFAULT_TO = process.env.CONTACT_TO || "safaoksuz@bilun.tech";

function escapeHtml(str: string): string {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

interface ResendPayload {
  from: string;
  to: string[];
  reply_to?: string;
  subject: string;
  html: string;
  text: string;
}

function sendEmailViaResend(apiKey: string, payload: ResendPayload): Promise<{ ok: boolean; status: number; data: any }> {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify(payload);

    const req = https.request(
      {
        hostname: "api.resend.com",
        path: "/emails",
        method: "POST",
        family: 4, // Force IPv4 to prevent IPv6 timeout issues on Linux
        timeout: 10000,
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(postData),
        },
      },
      (res) => {
        let responseBody = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          responseBody += chunk;
        });
        res.on("end", () => {
          let parsed: any;
          try {
            parsed = JSON.parse(responseBody);
          } catch {
            parsed = { raw: responseBody };
          }
          const isOk = (res.statusCode ?? 500) >= 200 && (res.statusCode ?? 500) < 300;
          resolve({ ok: isOk, status: res.statusCode ?? 500, data: parsed });
        });
      },
    );

    req.on("error", (err) => {
      reject(err);
    });

    req.on("timeout", () => {
      req.destroy(new Error("Resend request timed out"));
    });

    req.write(postData);
    req.end();
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();

    // Anti-spam honeypot
    if (body && body.website) {
      return NextResponse.json({ ok: true });
    }

    const {
      name,
      email,
      category = "general",
      message,
      systemInfo,
    } = body || {};

    if (!name || !email || !message) {
      return NextResponse.json(
        { error: "Ad, e-posta ve mesaj alanları zorunludur." },
        { status: 400 },
      );
    }

    const trimmedEmail = String(email).trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      return NextResponse.json(
        { error: "Lütfen geçerli bir e-posta adresi girin." },
        { status: 400 },
      );
    }

    const categoryLabels: Record<string, string> = {
      bug: "Hata Bildirimi (Bug)",
      sut: "SUT Kural / Fiyat Uyuşmazlığı",
      feature: "Öneri / Geliştirme Talebi",
      general: "Genel Geri Bildirim",
    };
    const categoryLabel = categoryLabels[category] || category;

    const apiKey = process.env.RESEND_API_KEY;

    const subject = `[Bilun Geri Bildirim] ${categoryLabel} - ${name}`;

    const diagnosticsHtml = systemInfo
      ? `<tr><td style="padding: 6px 0;"><strong>Aktif Sekme / Konum:</strong></td><td>${escapeHtml(systemInfo.activeTab || "-")}</td></tr>
         <tr><td style="padding: 6px 0;"><strong>Kullanıcı Rolü:</strong></td><td>${escapeHtml(systemInfo.role || "-")}</td></tr>
         <tr><td style="padding: 6px 0;"><strong>Sayfa URL:</strong></td><td>${escapeHtml(systemInfo.url || "-")}</td></tr>
         <tr><td style="padding: 6px 0;"><strong>Zaman:</strong></td><td>${escapeHtml(systemInfo.timestamp || new Date().toISOString())}</td></tr>`
      : "";

    const html = `
      <h2>Bilun Uygulama İçi Geri Bildirim</h2>
      <table style="border-collapse: collapse; width: 100%; max-width: 600px; font-family: sans-serif; font-size: 14px;">
        <tr><td style="padding: 6px 0; width: 160px;"><strong>Gönderen:</strong></td><td>${escapeHtml(name)}</td></tr>
        <tr><td style="padding: 6px 0;"><strong>E-posta:</strong></td><td><a href="mailto:${escapeHtml(trimmedEmail)}">${escapeHtml(trimmedEmail)}</a></td></tr>
        <tr><td style="padding: 6px 0;"><strong>Kategori:</strong></td><td>${escapeHtml(categoryLabel)}</td></tr>
        ${diagnosticsHtml}
      </table>
      <h3 style="margin-top: 20px; font-family: sans-serif;">Mesaj:</h3>
      <div style="background-color: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px; padding: 14px; font-family: sans-serif; font-size: 14px; line-height: 1.5; white-space: pre-wrap;">${escapeHtml(message)}</div>
    `;

    const text = `Bilun Uygulama İçi Geri Bildirim
========================================
Gönderen:  ${name}
E-posta:   ${trimmedEmail}
Kategori:  ${categoryLabel}
${systemInfo ? `Konum:     ${systemInfo.activeTab || "-"} (${systemInfo.url || "-"})\nRol:       ${systemInfo.role || "-"}\nZaman:     ${systemInfo.timestamp || new Date().toISOString()}\n` : ""}
Mesaj:
${message}
`;

    // Construct mailto fallback link
    const mailtoSubject = encodeURIComponent(subject);
    const mailtoBody = encodeURIComponent(text);
    const mailtoHref = `mailto:${DEFAULT_TO}?subject=${mailtoSubject}&body=${mailtoBody}`;

    // If RESEND_API_KEY is not configured (e.g. offline demo)
    if (!apiKey) {
      console.warn("RESEND_API_KEY is not set. Feedback logged locally:\n", text);
      return NextResponse.json({
        ok: true,
        delivered: false,
        warning: "RESEND_API_KEY_NOT_CONFIGURED",
        mailtoHref,
        message: "Mesaj yerel konsola kaydedildi. Gerçek e-posta için RESEND_API_KEY gereklidir.",
      });
    }

    const result = await sendEmailViaResend(apiKey, {
      from: DEFAULT_FROM,
      to: [DEFAULT_TO],
      reply_to: trimmedEmail,
      subject,
      html,
      text,
    });

    if (!result.ok) {
      console.error("Resend API error:", result.status, result.data);
      return NextResponse.json(
        {
          error: "E-posta servisi yanıt vermedi. Lütfen doğrudan safaoksuz@bilun.tech adresine yazın.",
          mailtoHref,
        },
        { status: 500 },
      );
    }

    return NextResponse.json({ ok: true, delivered: true, id: result.data?.id });
  } catch (error) {
    console.error("Feedback route error:", error);
    return NextResponse.json(
      { error: "Sunucu hatası oluştu. Lütfen tekrar deneyin." },
      { status: 500 },
    );
  }
}
