# Report Problems & User Feedback Modal Plan

## Goal
Add a "Report Problems / Sorun Bildir" button and modal dialog to Bilun, allowing users/evaluators trying the product to submit feedback, bugs, and SUT rule discrepancy notes directly to `safaoksuz@bilun.tech`, mirroring the email delivery architecture of the `bilun.tech` landing website.

---

## 1. Architecture Overview
- **Destination Email:** `safaoksuz@bilun.tech`
- **Email Delivery Provider:** Resend API (`RESEND_API_KEY`) with graceful fallback to `mailto:` link if key is not configured.
- **Components:**
  - `frontend/src/components/feedback/ReportProblemModal.tsx` (accessible, theme-aware feedback dialog)
  - `frontend/src/app/api/feedback/route.ts` (Next.js server-side endpoint)
  - Triggers in `AppSidebar.tsx` and `WorkspaceTabStrip.tsx`

---

## 2. Implementation Steps
1. Add `showReportProblem` and `setShowReportProblem` to `NavigationStore`.
2. Implement `/api/feedback` route handler in Next.js.
3. Build `ReportProblemModal` component with validation, loading spinner, and success/fallback states.
4. Add trigger buttons in `AppSidebar` and `WorkspaceTabStrip`.
5. Add Turkish and English localization keys.
6. Write unit tests for store and modal components.
7. Verify with vitest, tsc, and next build.
