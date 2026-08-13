const shell = {
  skipToContent: "Ana içeriğe geç",
  locale: {
    groupLabel: "Dil",
    en: "İngilizce",
    tr: "Türkçe",
  },
  appSidebar: {
    ariaNavigation: "Bilun gezinme",
    logoAlt: "Bilun",
    ariaHomeTabs: "SUT ana sekmeler",
    howItWorks: "Nasıl çalışır",
    collapse: "Kenar çubuğunu daralt",
    expand: "Kenar çubuğunu genişlet",
  },
  role: {
    groupLabel: "Rol",
    billing_officer: "Faturalama Görevlisi",
    dev: "Geliştirici",
  },
  workspaceTabs: {
    ariaLabel: "Açık çalışma alanları",
    close: "Sekmeyi kapat",
    overflow: "Diğer açık sekmeler",
    openSideBySide: "Yan yana aç",
    closeSplit: "Bölünmüş görünümü kapat",
    swapPanes: "Bölmeleri değiştir",
  },
  quickOpen: {
    ariaLabel: "Hızlı hasta aç",
    placeholder: "Hasta no ara… (Ctrl+K)",
    empty: "Eşleşen hasta yok",
  },
} as const;

export default shell;
