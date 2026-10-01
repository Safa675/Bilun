const auth = {
  login: {
    title: "Geliştirici girişi",
    subtitle: "Geliştirici hesabınızla giriş yapın.",
    developerSignIn: "Geliştirici girişi",
    returnToBilling: "Faturalamaya dön",
    notDeveloper: "Bu hesabın geliştirici erişimi yok.",
    username: "Kullanıcı adı",
    password: "Parola",
    submit: "Giriş yap",
    submitting: "Giriş yapılıyor…",
    error: "Geçersiz kullanıcı adı veya parola.",
    notConfigured: "Bu sunucuda giriş yapılandırılmamış.",
    networkError: "Sunucuya ulaşılamadı. Lütfen tekrar deneyin.",
  },
  logout: {
    button: "Çıkış yap",
    error: "Çıkış doğrulanamadı. Lütfen tekrar deneyin.",
  },
} as const;

export default auth;
