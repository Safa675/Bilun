import { describe, expect, it } from "vitest";
import en from "@/messages/en/index";
import tr from "@/messages/tr/index";
import { translate } from "./translate";

describe("Phase4 plain language", () => {
  it("removes internal implementation wording in both locales", () => {
    const enCopy = JSON.stringify([en.patient, en.optimizer, en.app]);
    for (const phrase of ["exact-only", "surviving", "routes into", "algorithms", "composes", "python -m", "IHP"]) {
      expect(enCopy).not.toContain(phrase);
    }
    const trCopy = JSON.stringify([tr.patient, tr.optimizer, tr.app]);
    for (const phrase of ["hayatta kalan", "algoritmaları için", "devir teslimi", "python -m", "IHP"]) {
      expect(trCopy).not.toContain(phrase);
    }
  });

  it("keeps every new interface and glossary key available in both locales", () => {
    const groups = ["modules", "exemptionCategories"] as const;
    for (const group of groups) {
      expect(Object.keys(en.optimizer[group]).sort()).toEqual(Object.keys(tr.optimizer[group]).sort());
      for (const key of Object.keys(en.optimizer[group])) {
        const path = `optimizer.${group}.${key}`;
        expect(translate(en, path)).not.toBe(path);
        expect(translate(tr, path)).not.toBe(path);
      }
    }
    for (const key of Object.keys(en.billing.glossary)) {
      expect(translate(en, `billing.glossary.${key}`)).not.toBe(`billing.glossary.${key}`);
      expect(translate(tr, `billing.glossary.${key}`)).not.toBe(`billing.glossary.${key}`);
    }
    expect(en.billing.glossary.unavailable).toContain("does not mean a zero amount");
    expect(tr.billing.glossary.unavailable).toContain("Sıfır tutar");
    expect(en.billing.glossary.claimBacked).toContain("not a payment approval");
    expect(tr.billing.glossary.exact).toContain("Ödeme onayı anlamına gelmez");
    expect(en.billing.glossary.notApplicable).toContain("not a passed check");
    expect(tr.billing.glossary.notApplicable).toContain("Başarılı kontrol anlamına gelmez");
  });
});
