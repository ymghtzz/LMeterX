/**
 * @file useI18n.ts
 * @description Custom hook for internationalization
 * @author Charm
 * @copyright 2025
 */
import { useTranslation } from 'react-i18next';

export const useI18n = () => {
  const { t, i18n } = useTranslation();

  const formatMessage = (key: string, options?: any) => {
    return t(key, options);
  };

  const changeLanguage = (language: string) => {
    return i18n.changeLanguage(language);
  };

  const getCurrentLanguage = () => {
    return i18n.language;
  };

  return {
    t,
    formatMessage,
    changeLanguage,
    getCurrentLanguage,
    isReady: i18n.isInitialized,
  };
};

export default useI18n;
