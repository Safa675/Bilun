const auth = {
  login: {
    title: "Giriş",
    subtitle: "Bilun kullanıcı adınız ve parolanızla giriş yapın.",
    developerSignIn: "Geliştirici girişi",
    returnToBilling: "Faturalamaya dön",
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
