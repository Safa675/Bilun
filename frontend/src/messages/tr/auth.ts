const auth = {
  login: {
    title: "BILUN'a giriş yapın",
    subtitle: "Devam etmek için ortak kimlik bilgilerini girin.",
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
  },
} as const;

export default auth;
