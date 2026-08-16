## Task: Alibaba Token Plan API Key & Model Configuration (Local & Deployment)

### Goal
Configure the Alibaba Token Plan OpenAI-compatible endpoint, API key (`sk-sp-H...`), and DeepSeek v4 Flash model (`deepseek-v4-flash-0731`) for both local development and deployed production environments, ensuring robust endpoint resolution and end-to-end streaming verification.

### Subtasks
- [x] Update local `.env` with the Alibaba Token Plan API key, endpoint (`https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions`), and model (`deepseek-v4-flash-0731`).
- [x] Enhance `src/bilun/chatbot/llm.py` to support dynamic endpoint resolution (handling both `LLM_ENDPOINT` and `LLM_BASE_URL` with auto `/chat/completions` suffixing) and default model `deepseek-v4-flash-0731`.
- [x] Update `.env.example` and `plans/deployment/vps-deploy-plan.md` to reflect Alibaba Token Plan configuration.
- [x] Verify live chat completions and streaming against the Alibaba Token Plan API.
- [x] Run backend unit tests (`pytest`) and frontend tests (`vitest`) to verify 100% green status.
- [x] Document the live VPS update instructions for the deployed instance.

### Out of Scope
- Modifying non-LLM billing or rules engine logic.

## Task: Tab Etiketi Düzeltmeleri (Gelir Dashboard + font standardizasyonu)

### Goal
"Gelir" sekme etiketini "Gelir Dashboard" yapmak ve Uyumluluk sekmesinin tipografisini uygulamanın geri kalanıyla aynı hizaya getirmek.

### Doğrulanan Bulgular (keşif)
- Render edilen sekme etiketi kaynağı `constants.homeTabs.revenue.label` (AppSidebar, page.tsx activeTabLabel, workspaceSubtabs.resolveTabInfo). `billing.views.revenue.shortTitle` zaten "Gelir Dashboard" — doğru yer orası değil.
- Uygulama standardı: tüm Fraunces display başlıklar `font-medium` (Section, PatientFinancialSummary, OriginalBillView, SutPatientWorkspace). Tek sapma: `SUTComplianceDashboard.tsx:68` → `font-bold`.
- Sayı standardı: `font-semibold` + `tabular-nums` (Stat, KpiCard, MedulaRejectionQueueTab). Compliance üst panel KPI'ları `font-bold font-mono` kullanıyor.
- `SutInlineAIPanel.resolvePromptKey` etiket string'ini chat prompt anahtarına eşliyor — yeniden adlandırma buraya da yayılmalı (yoksa Gelir sekmesi `sutWorkspace` fallback'ine düşer).

### Subtasks
- [x] Keşif: etiket kaynakları + font sapmalarını doğrula
- [x] i18n yeniden adlandırma: tr/en `constants.homeTabs.revenue.label` → "Gelir Dashboard" / "Revenue Dashboard"
- [x] Legacy kalıntıları hizala: tr/en `home.tabRevenue`, `lib/constants.ts` SUT_HOME_TABS revenue.label
- [x] `SutInlineAIPanel.resolvePromptKey` map güncelle (Gelir/Revenue → Dashboard anahtarları)
- [x] `workspaceSubtabs.test.ts` mock + assertion güncelle
- [x] Font standardizasyonu: SUTComplianceDashboard h2 `font-bold`→`font-medium`; KPI değerleri `font-bold`→`font-semibold tabular-nums`
- [x] Doğrulama: vitest (frontend testleri) + tsc/lint

### Review
- vitest: 47 dosya / 243 test yeşil; `tsc --noEmit` temiz; eslint değiştirilen dosyalarda yeni sorun üretmedi.
- Mevcut (bu değişiklikten bağımsız) lint bulguları: `SutInlineAIPanel.tsx:314` react-hooks/refs hatası HEAD'de de var; `SUTComplianceDashboard.tsx` kullanılmayan importlar (`useState/useEffect/useMemo`, `t`) — devam eden redesign dosyası, dokunulmadı.
- Renk sapmaları ayrıca not edildi: compliance üst paneli Tailwind palet renkleri (`text-emerald-400` vb.) ve tanımsız `--text-tertiary` token'ı kullanıyor — kilitli navy/gold paletiyle uyumsuz; ayrı iş olarak ele alınmalı.
- Commit/push yapılmadı: çalışma ağacı kullanıcının devam eden compliance redesign değişiklikleriyle iç içe; karar kullanıcıda.

### Out of Scope
- Görünüm içeriği / KPI / eylem listesi değişiklikleri.
- Renk paleti sapmaları (`text-emerald-400` vb. Tailwind renkleri, tanımsız `--text-tertiary` token'ı) — ayrı iş; kullanıcıya raporlanacak.
- Commit/push/PR kararı kullanıcıda (çalışma ağacında devam eden compliance redesign değişiklikleri var).
