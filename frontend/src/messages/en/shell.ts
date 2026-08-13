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
} as const;

export default shell;
