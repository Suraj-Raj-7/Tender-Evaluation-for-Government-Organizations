/**
 * frontend/src/i18n.js
 * ------------------------
 * Purpose: Configures react-i18next -- loads the English and Hindi
 * translation files, and restores whichever language the user
 * previously picked (saved in localStorage) so it persists across
 * browser refreshes, per the Phase Guide's "language persistence" spec.
 *
 * Where it's used: imported once, in main.jsx, before the app renders.
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import hi from "./locales/hi.json";

const savedLanguage = localStorage.getItem("tenderiq_language") || "en";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
  },
  lng: savedLanguage,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;