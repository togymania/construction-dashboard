/**
 * Translation strings for the UI.
 *
 * Add a key to BOTH locales. If a TR key is missing, the EN fallback is used.
 * Keys are dot-notation: t("nav.dashboard"), t("buttons.save"), etc.
 *
 * NOTE: This is the source of truth for user-facing text. Backend-generated
 * messages (insights, error responses) are still produced server-side and
 * remain in English for now.
 */
export const translations = {
  EN: {
    // Navigation (sidebar + breadcrumbs)
    nav: {
      dashboard: "Dashboard",
      projects: "Projects",
      subcontractors: "Subcontractors",
      workforce: "Workforce",
      schedule: "Schedule",
      risks: "Risks",
      reports: "Reports",
      settings: "Settings",
      budgetCategories: "Budget Categories",
      logout: "Logout",
    },

    // Header
    header: {
      search: "Search...",
      notifications: "Notifications",
      changeLanguage: "Change language",
      changeTheme: "Toggle theme",
      profile: "Profile",
    },

    // Common buttons & actions
    buttons: {
      save: "Save",
      cancel: "Cancel",
      delete: "Delete",
      edit: "Edit",
      close: "Close",
      create: "Create",
      upload: "Upload",
      download: "Download",
      refresh: "Refresh",
      filter: "Filter",
      search: "Search",
      apply: "Apply",
      reset: "Reset",
      confirm: "Confirm",
      back: "Back",
      next: "Next",
      view: "View",
      add: "Add",
      remove: "Remove",
    },

    // Common status / states
    status: {
      loading: "Loading...",
      noData: "No data",
      error: "Error",
      success: "Success",
      active: "Active",
      completed: "Completed",
      draft: "Draft",
      terminated: "Terminated",
      suspended: "Suspended",
      blacklisted: "Blacklisted",
      pending: "Pending",
      approved: "Approved",
      paid: "Paid",
      rejected: "Rejected",
      overdue: "Overdue",
    },

    // Page titles
    pages: {
      dashboard: "Dashboard",
      projects: "Projects",
      projectsSubtitle: "Construction portfolio overview",
      subcontractors: "Subcontractors",
      subcontractorsSubtitle: "Manage contractors, contracts, and payments",
      workforce: "Workforce Intelligence",
      workforceSubtitle: "Real-time personnel analytics — direct, subcontractor, and discipline breakdowns.",
      budget: "Budget",
      schedule: "Schedule",
      risks: "Risks",
      reports: "Reports",
      comingSoon: "Coming Soon",
    },

    // Subcontractor specific
    subs: {
      newSubcontractor: "New Subcontractor",
      totalSubcontractors: "Total Subcontractors",
      activeContracts: "Active Contracts",
      overdueContracts: "Overdue",
      totalContractValue: "Total Contract Value",
      paymentProgress: "Payment Progress",
      paid: "paid",
      overdueLabel: "overdue",
      paymentsByStatus: "Payments by Status",
      topByValue: "Top 5 Subcontractors by Value",
      monthlyPayments: "Monthly Payments (Last 6 Months)",
      aggregateForecast: "Cash Flow — 3-Month Aggregate Forecast",
      contracts: "Contracts",
      documents: "Documents",
      cashFlow: "Cash Flow",
      aiInsights: "AI Insights",
      overview: "Overview",
      searchPlaceholder: "Search by name, tax ID, contact...",
      allStatuses: "All statuses",
      allSpecializations: "All specializations...",
    },

    // Workforce specific
    workforce: {
      uploadExcel: "Upload Excel",
      dailyTrend: "Daily Workforce Trend",
      weeklyAverage: "Weekly Average",
      lastNDays: "Last {n} days",
      direct: "Direct",
      indirect: "Indirect",
      subcontractor: "Subcontractor",
      total: "Total Workforce",
    },

    // Forecast / chart labels
    forecast: {
      confidence: "Confidence",
      activeOf: "{active} active / {total} subcontractors",
      likelyTotal: "Likely total",
      actual: "Actual",
      best: "Best",
      likely: "Likely",
      worst: "Worst",
      uncertainty: "Uncertainty",
      today: "Today",
    },
  },

  TR: {
    nav: {
      dashboard: "Panel",
      projects: "Projeler",
      subcontractors: "Taşeronlar",
      workforce: "İşgücü",
      schedule: "Takvim",
      risks: "Riskler",
      reports: "Raporlar",
      settings: "Ayarlar",
      budgetCategories: "Bütçe Kategorileri",
      logout: "Çıkış",
    },

    header: {
      search: "Ara...",
      notifications: "Bildirimler",
      changeLanguage: "Dil değiştir",
      changeTheme: "Temayı değiştir",
      profile: "Profil",
    },

    buttons: {
      save: "Kaydet",
      cancel: "İptal",
      delete: "Sil",
      edit: "Düzenle",
      close: "Kapat",
      create: "Oluştur",
      upload: "Yükle",
      download: "İndir",
      refresh: "Yenile",
      filter: "Filtre",
      search: "Ara",
      apply: "Uygula",
      reset: "Sıfırla",
      confirm: "Onayla",
      back: "Geri",
      next: "İleri",
      view: "Görüntüle",
      add: "Ekle",
      remove: "Kaldır",
    },

    status: {
      loading: "Yükleniyor...",
      noData: "Veri yok",
      error: "Hata",
      success: "Başarılı",
      active: "Aktif",
      completed: "Tamamlandı",
      draft: "Taslak",
      terminated: "Feshedildi",
      suspended: "Askıda",
      blacklisted: "Kara liste",
      pending: "Beklemede",
      approved: "Onaylandı",
      paid: "Ödendi",
      rejected: "Reddedildi",
      overdue: "Gecikmiş",
    },

    pages: {
      dashboard: "Panel",
      projects: "Projeler",
      projectsSubtitle: "İnşaat portföyü genel görünümü",
      subcontractors: "Taşeronlar",
      subcontractorsSubtitle: "Taşeron, sözleşme ve ödeme yönetimi",
      workforce: "İşgücü Analitiği",
      workforceSubtitle: "Gerçek zamanlı personel analitiği — direkt, taşeron ve disiplin kırılımları.",
      budget: "Bütçe",
      schedule: "Takvim",
      risks: "Riskler",
      reports: "Raporlar",
      comingSoon: "Yakında",
    },

    subs: {
      newSubcontractor: "Yeni Taşeron",
      totalSubcontractors: "Toplam Taşeron",
      activeContracts: "Aktif Sözleşme",
      overdueContracts: "Geciken",
      totalContractValue: "Toplam Sözleşme Değeri",
      paymentProgress: "Ödeme İlerlemesi",
      paid: "ödendi",
      overdueLabel: "gecikmiş",
      paymentsByStatus: "Ödemeler — Durum",
      topByValue: "Değere Göre İlk 5 Taşeron",
      monthlyPayments: "Aylık Ödemeler (Son 6 Ay)",
      aggregateForecast: "Nakit Akışı — 3 Aylık Toplam Tahmin",
      contracts: "Sözleşmeler",
      documents: "Dokümanlar",
      cashFlow: "Nakit Akışı",
      aiInsights: "AI Yorumları",
      overview: "Genel Bakış",
      searchPlaceholder: "İsim, vergi no, iletişim ara...",
      allStatuses: "Tüm durumlar",
      allSpecializations: "Tüm uzmanlıklar...",
    },

    workforce: {
      uploadExcel: "Excel Yükle",
      dailyTrend: "Günlük İşgücü Trendi",
      weeklyAverage: "Haftalık Ortalama",
      lastNDays: "Son {n} gün",
      direct: "Direkt",
      indirect: "Endirekt",
      subcontractor: "Taşeron",
      total: "Toplam İşgücü",
    },

    forecast: {
      confidence: "Güven",
      activeOf: "{active} aktif / {total} taşeron",
      likelyTotal: "Olası toplam",
      actual: "Gerçekleşen",
      best: "En iyi",
      likely: "Olası",
      worst: "En kötü",
      uncertainty: "Belirsizlik",
      today: "Bugün",
    },
  },
} as const;

export type Locale = keyof typeof translations;
export const SUPPORTED_LOCALES: Locale[] = ["EN", "TR"];
