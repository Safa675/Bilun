import { describe, expect, it } from "vitest";
import {
  resolveTabInfo,
  BILLING_SUB_ICONS,
  COMPLIANCE_SUB_ICONS,
  RULE_DATABASE_SUB_ICONS,
} from "./workspaceSubtabs";
import { workspaceTabId, type WorkspaceTab } from "./workspaceTabs";

function makeTab(
  kind: "section" | "patient",
  refId: string,
  query?: string,
): WorkspaceTab {
  return {
    id: workspaceTabId(kind, refId),
    kind,
    refId,
    query,
    lastActivatedAt: Date.now(),
  };
}

// Mock translator that reflects keys
const mockT = (key: string) => {
  const map: Record<string, string> = {
    "constants.homeTabs.patients.label": "Hastalar",
    "constants.homeTabs.compliance.label": "Uyumluluk",
    "constants.homeTabs.revenue.label": "Gelir",
    "constants.homeTabs.operations.label": "Operasyonlar",
    "constants.homeTabs.referenceTools.label": "Referans Araçları",
    "constants.homeTabs.ruleDatabase.label": "Kural Veritabanı",

    "sections.tools.subs.validator": "Talep Doğrulayıcı",
    "sections.tools.subs.search": "Malzeme Arama",
    "sections.tools.subs.bundled": "Paket Kalemler",
    "sections.tools.subs.priceHistory": "Fiyat Geçmişi",
    "sections.tools.subs.visits": "Ziyaret Fiyatlandırması",
    "sections.tools.subs.drugs": "İlaç Kataloğu",
    "sections.tools.subs.specialty": "Branşa Göre",
    "sections.tools.subs.labPrices": "Laboratuvar Fiyatları",

    "optimizer.tabs.exemptions": "Katılım payı muafiyetleri",
    "optimizer.tabs.surcharge": "Fark ücreti uyumu",

    "sections.ruleDatabase.tabs.rules": "Kurallar",
    "sections.ruleDatabase.tabs.sections": "Bölümler",
    "sections.ruleDatabase.tabs.clauses": "Hükümler",
    "sections.ruleDatabase.tabs.prose": "Düz metin motorları",
    "sections.ruleDatabase.tabs.deferrals": "Ertelenenler",
  };
  return map[key] ?? key;
};

describe("resolveTabInfo", () => {
  describe("Patient tabs", () => {
    it("returns the patient ID without subtabs", () => {
      const tab = makeTab("patient", "P-1001");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("P-1001");
      expect(info.fullTitle).toBe("P-1001");
      expect(info.subtab).toBeNull();
    });
  });

  describe("Reference Tools subtabs", () => {
    it("defaults to validator (Talep Doğrulayıcı) when no subtab is in query", () => {
      const tab = makeTab("section", "reference-tools");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Talep Doğrulayıcı");
      expect(info.fullTitle).toBe("Referans Araçları · Talep Doğrulayıcı");
      expect(info.Icon).toBe(BILLING_SUB_ICONS.validator);
      expect(info.subtab).toBe("validator");
    });

    it("resolves specialty (Branşa Göre) when toolSub=specialty", () => {
      const tab = makeTab("section", "reference-tools", "tab=reference-tools&toolSub=specialty");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Branşa Göre");
      expect(info.fullTitle).toBe("Referans Araçları · Branşa Göre");
      expect(info.Icon).toBe(BILLING_SUB_ICONS.specialty);
      expect(info.subtab).toBe("specialty");
    });

    it("resolves search (Malzeme Arama) when toolSub=search", () => {
      const tab = makeTab("section", "reference-tools", "tab=reference-tools&toolSub=search");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Malzeme Arama");
      expect(info.Icon).toBe(BILLING_SUB_ICONS.search);
      expect(info.subtab).toBe("search");
    });

    it("resolves drugs (İlaç Kataloğu) when toolSub=drugs", () => {
      const tab = makeTab("section", "reference-tools", "tab=reference-tools&toolSub=drugs");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("İlaç Kataloğu");
      expect(info.Icon).toBe(BILLING_SUB_ICONS.drugs);
    });

    it("resolves lab_prices (Laboratuvar Fiyatları) when toolSub=lab_prices", () => {
      const tab = makeTab("section", "reference-tools", "tab=reference-tools&toolSub=lab_prices");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Laboratuvar Fiyatları");
      expect(info.Icon).toBe(BILLING_SUB_ICONS.lab_prices);
    });
  });

  describe("Compliance subtabs", () => {
    it("defaults to exemptions (Katılım payı muafiyetleri)", () => {
      const tab = makeTab("section", "compliance");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Katılım payı muafiyetleri");
      expect(info.fullTitle).toBe("Uyumluluk · Katılım payı muafiyetleri");
      expect(info.Icon).toBe(COMPLIANCE_SUB_ICONS.exemptions);
      expect(info.subtab).toBe("exemptions");
    });

    it("resolves surcharge (Fark ücreti uyumu) when compTab=surcharge", () => {
      const tab = makeTab("section", "compliance", "tab=compliance&compTab=surcharge");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Fark ücreti uyumu");
      expect(info.fullTitle).toBe("Uyumluluk · Fark ücreti uyumu");
      expect(info.Icon).toBe(COMPLIANCE_SUB_ICONS.surcharge);
      expect(info.subtab).toBe("surcharge");
    });
  });

  describe("Rule Database subtabs", () => {
    it("defaults to rules (Kurallar)", () => {
      const tab = makeTab("section", "rule-database");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Kurallar");
      expect(info.fullTitle).toBe("Kural Veritabanı · Kurallar");
      expect(info.Icon).toBe(RULE_DATABASE_SUB_ICONS.rules);
      expect(info.subtab).toBe("rules");
    });

    it("resolves clauses (Hükümler) when rdTab=clauses", () => {
      const tab = makeTab("section", "rule-database", "tab=rule-database&rdTab=clauses");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Hükümler");
      expect(info.fullTitle).toBe("Kural Veritabanı · Hükümler");
      expect(info.Icon).toBe(RULE_DATABASE_SUB_ICONS.clauses);
      expect(info.subtab).toBe("clauses");
    });

    it("resolves sections (Bölümler) when rdTab=sections", () => {
      const tab = makeTab("section", "rule-database", "tab=rule-database&rdTab=sections");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Bölümler");
      expect(info.Icon).toBe(RULE_DATABASE_SUB_ICONS.sections);
    });

    it("resolves prose (Düz metin motorları) when rdTab=prose", () => {
      const tab = makeTab("section", "rule-database", "tab=rule-database&rdTab=prose");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Düz metin motorları");
      expect(info.Icon).toBe(RULE_DATABASE_SUB_ICONS.prose);
    });

    it("resolves deferrals (Ertelenenler) when rdTab=deferrals", () => {
      const tab = makeTab("section", "rule-database", "tab=rule-database&rdTab=deferrals");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Ertelenenler");
      expect(info.Icon).toBe(RULE_DATABASE_SUB_ICONS.deferrals);
    });
  });

  describe("Standard parent section tabs without subtabs", () => {
    it("returns parent title and icon for patients tab", () => {
      const tab = makeTab("section", "patients");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Hastalar");
      expect(info.fullTitle).toBe("Hastalar");
      expect(info.subtab).toBeNull();
    });

    it("returns parent title and icon for revenue tab", () => {
      const tab = makeTab("section", "revenue");
      const info = resolveTabInfo(tab, mockT);
      expect(info.label).toBe("Gelir");
      expect(info.fullTitle).toBe("Gelir");
      expect(info.subtab).toBeNull();
    });
  });
});
