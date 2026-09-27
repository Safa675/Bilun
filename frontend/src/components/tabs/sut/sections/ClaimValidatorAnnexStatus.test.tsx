import { describe, expect, it } from "vitest";
import { renderToStaticMarkupWithLocale } from "@/test/renderWithLocale";
import { useT } from "@/lib/i18n/useTranslations";
import type { SutMaterialLine } from "@/lib/api/sut";
import { MaterialLineRow } from "./ClaimValidatorSection";

const line: SutMaterialLine = {
  material_name: "Conditional material", material_code: "CODE", quantity: 1,
  unit_price: 100, total_price: 100, is_reimbursable: null, is_bundled: null,
  source: "billed", exactness_status: "exact", notes: "",
};

function Row({ value = line }: { value?: SutMaterialLine }) {
  return <table><tbody><MaterialLineRow line={value} t={useT()} /></tbody></table>;
}

describe("legacy material annex status", () => {
  it("keeps unknown exclusion and bundling neutral instead of displaying yes/no", () => {
    const html = renderToStaticMarkupWithLocale(<Row />);
    expect(html.match(/Applicability unconfirmed/g)).toHaveLength(2);
    expect(html).not.toContain(">Yes<");
    expect(html).not.toContain(">No<");
    expect(html).not.toContain(">Bundled<");
  });

  it("renders both unknown statuses in Turkish", () => {
    const html = renderToStaticMarkupWithLocale(<Row />, "tr");
    expect(html.match(/Uygulanabilirlik doğrulanmadı/g)).toHaveLength(2);
  });

  it("retains known boolean display", () => {
    const html = renderToStaticMarkupWithLocale(<Row value={{ ...line, is_reimbursable: true, is_bundled: false }} />);
    expect(html).toContain(">Yes<");
    expect(html).toContain(">No<");
    expect(html).not.toContain("Applicability unconfirmed");
  });
});
