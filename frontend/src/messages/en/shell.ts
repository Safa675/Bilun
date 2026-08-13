const shell = {
  skipToContent: "Skip to main content",
  locale: {
    groupLabel: "Language",
    en: "English",
    tr: "Turkish",
  },
  appSidebar: {
    ariaNavigation: "Bilun navigation",
    logoAlt: "Bilun",
    ariaHomeTabs: "SUT home tabs",
    howItWorks: "How it works",
    collapse: "Collapse sidebar",
    expand: "Expand sidebar",
  },
  role: {
    groupLabel: "Role",
    billing_officer: "Billing Officer",
    dev: "Developer",
  },
  workspaceTabs: {
    ariaLabel: "Open workspaces",
    close: "Close tab",
    overflow: "More open tabs",
    openSideBySide: "Open side by side",
    closeSplit: "Close split view",
    swapPanes: "Swap panes",
  },
  quickOpen: {
    ariaLabel: "Quick open patient",
    placeholder: "Search patient id… (Ctrl+K)",
    empty: "No matching patients",
  },
} as const;

export default shell;
