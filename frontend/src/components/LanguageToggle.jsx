/**
 * frontend/src/components/LanguageToggle.jsx
 * -----------------------------------------------
 * Purpose: A simple EN | HI button pair. Switches the whole app's
 * language instantly, and remembers the choice across browser
 * refreshes.
 *
 * Where it gets its data: i18next's current active language.
 * Where it's used: rendered once, inside AppLayout's header, so it
 * appears on every page.
 */

import { useTranslation } from "react-i18next";
import { Button, Space } from "antd";

function LanguageToggle() {
  const { i18n } = useTranslation();

  /**
   * Purpose: Switches the active language and saves the choice to
   * localStorage, so i18n.js can restore it on the next page load
   * (per the Phase Guide's "language persistence" requirement).
   *
   * Where it's used: called by the EN/HI buttons below, on click.
   */
  function changeLanguage(lang) {
    i18n.changeLanguage(lang);
    localStorage.setItem("tenderiq_language", lang);
  }

  return (
    <Space>
      <Button
        type={i18n.language === "en" ? "primary" : "default"}
        size="small"
        onClick={() => changeLanguage("en")}
      >
        English
      </Button>
      <Button
        type={i18n.language === "hi" ? "primary" : "default"}
        size="small"
        onClick={() => changeLanguage("hi")}
      >
        हिंदी
      </Button>
    </Space>
  );
}

export default LanguageToggle;