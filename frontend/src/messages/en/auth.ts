const auth = {
  login: {
    title: "Developer sign in",
    subtitle: "Sign in with your developer account.",
    developerSignIn: "Developer sign in",
    returnToBilling: "Return to billing",
    notDeveloper: "This account does not have developer access.",
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
