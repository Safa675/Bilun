const auth = {
  login: {
    title: "Sign in to BILUN",
    subtitle: "Enter the shared credentials to continue.",
    username: "Username",
    password: "Password",
    submit: "Sign in",
    submitting: "Signing in…",
    error: "Invalid username or password.",
    notConfigured: "Sign-in is not configured on this server.",
    networkError: "Could not reach the server. Please retry.",
  },
  logout: {
    button: "Sign out",
  },
} as const;

export default auth;
