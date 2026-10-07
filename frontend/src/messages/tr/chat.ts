const chat = {
  title: "Bilun Analizi",
  subtitle: {
    patient: "Hasta: {patientId}",
    cohortOverview: "Kohort özeti",
  },
  actions: {
    retryQuestion: "Soruyu yeniden dene",
    regenerateAnalysis: "Analizi yenile",
    centerInline: "Ortala (satır içi)",
    dockRight: "Sağa sabitle",
    sendMessage: "Mesaj gönder",
    collapse: "Sohbeti küçült",
    expand: "Sohbeti aç",
  },
  collapsed: {
    prompt: "Bilun'a sorun…",
    working: "Bilun çalışıyor…",
  },
  emptyState: "Bilun her görünümü özetler ve tüm konuşmayı burada tutar.",
  devModeBadge: "Geliştirici",
  roles: {
    you: "Siz",
    bilun: "Bilun",
  },
  loading: {
    analyzing: "Bilun analiz ediyor...",
    thinking: "Düşünüyor",
  },
  errors: {
    interruptedFollowUp: "Son sorunun yanıtı tamamlanmadı. Hazır olduğunuzda tekrar deneyin.",
    failedAutoAnalysis: "SUT analizi alınamadı. Yeniden denemek için yenileye tıklayın.",
    failedFollowUp: "SUT yanıtı alınamadı.",
    questionTooLong: "Sorunuz çok uzun. {max} karakter veya daha az olacak şekilde kısaltıp tekrar deneyin.",
  },
  tip: {
    label: "İpucu:",
    selectPatient:
      "Katılım payı tasarrufu, laboratuvar optimizasyonu, ilaç ikamesi ve fatura stratejisi karşılaştırmaları dahil ayrıntılı fatura analizi için kohort tablosundan bir hasta seçin.",
  },
  input: {
    placeholderPatient: "Bu hasta veya fatura incelemesi hakkında Bilun'a sorun...",
    placeholderWorkspace: "Bu çalışma alanı hakkında Bilun'a sorun...",
  },
  defaultPrompts: {
    sutWorkspace:
      "Mevcut SUT çalışma alanını özetleyin. Burada hangi kural inceleme iş akışlarının kullanılabildiğini ve kullanıcının önce neye bakması gerektiğini vurgulayın. Türkçe yanıt verin.",
    patients:
      "Hasta kohort dizinini özetleyin. Bir hastaya girmeden önce geri kazanılabilir toplamlara, öncelikli hastalara ve kesinlik uyarılarına odaklanın. Türkçe yanıt verin.",
    compliance:
      "Filtrelenmiş kohort için uyumluluk uyarılarını özetleyin. Katılım payı muafiyeti (EK-1A), fark ücreti bayrakları (EK-2G), EK-2C-1 katılım payı oranı uyumsuzlukları ve kesinlik engellerini vurgulayın. Türkçe yanıt verin.",
    revenue:
      "Filtrelenmiş kohort için gelir geri kazanımını özetleyin. Geri kazanılabilir toplamları, öncelikli hastaları ve kesinlik sınırlamalarını vurgulayın. Türkçe yanıt verin.",
    operations:
      "MEDULA red kuyruğunu özetleyin. Bekleyen retleri, hata kodu kategorilerini ve yeniden gönderim öncesi düzeltici adımları vurgulayın. Türkçe yanıt verin.",
    referenceTools:
      "Hangi tebliğ referans araçlarının mevcut olduğunu ve bir fatura görevlisinin her sorguyu ne zaman kullanması gerektiğini açıklayın. Türkçe yanıt verin.",
    ruleDatabase:
      "SUT kural veritabanını özetleyin. Kuralların kaynak hükümlere ve EK listelere nasıl eşlendiğini, kapsam durumlarının ne anlama geldiğini ve hangi kurallarda hâlâ boşluk olduğunu açıklayın. Türkçe yanıt verin.",
    sutPatientWorkspace:
      "Hasta düzeyinde SUT brifingi verin. Kural hesaplama durumunu, kesinlik odaklı optimizasyon bulgularını ve fatura incelemesinde doğrulanması gerekenleri özetleyin. Türkçe yanıt verin.",
    sutBillingReview:
      "Bu SUT fatura incelemesini özetleyin. Hangi bölümlerin kesin olduğunu, hangilerinin kullanılamadığını ve kullanıcının işlem öncesi neyi doğrulaması gerektiğini açıklayın. Türkçe yanıt verin.",
  },
  api: {
    requestTimedOut: "SUT sohbet isteği zaman aşımına uğradı. Lütfen tekrar deneyin.",
    couldNotReachApi: "API'ye ulaşılamadı: {url}",
    failedWithBody: "SUT sohbet hatası: {status} {statusText} - {body}",
    failedWithoutBody: "SUT sohbet hatası: {status} {statusText}",
    noResponseBody: "SUT sohbet yanıt gövdesi döndürmedi.",
    noResponseReceived: "SUT sohbetten yanıt alınamadı. Lütfen tekrar deneyin.",
    emptyResponse: "SUT sohbet boş yanıt döndürdü.",
  },
} as const;

export default chat;
