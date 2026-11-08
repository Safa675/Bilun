const auth = {
  login: {
    title: "Sign in",
    subtitle: "Sign in with your Bilun username and password.",
    developerSignIn: "Developer sign in",
    returnToBilling: "Return to billing",
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
    error: "Could not confirm sign-out. Please try again.",
  },
} as const;

export default auth;
