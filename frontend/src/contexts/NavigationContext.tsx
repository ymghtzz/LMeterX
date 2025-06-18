/**
 * @file NavigationContext.tsx
 * @description Navigation context for the frontend
 * @author Charm
 * @copyright 2025
 * */

import React, { createContext, useContext, useMemo, useRef } from 'react';

interface NavigationContextType {
  lastNavigationTime: React.MutableRefObject<number>;
  registerNavigation: () => void;
}

const NavigationContext = createContext<NavigationContextType | undefined>(
  undefined
);

export const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const lastNavigationTime = useRef<number>(Date.now());

  const registerNavigation = () => {
    lastNavigationTime.current = Date.now();
  };

  const contextValue = useMemo(
    () => ({ lastNavigationTime, registerNavigation }),
    []
  );

  return (
    <NavigationContext.Provider value={contextValue}>
      {children}
    </NavigationContext.Provider>
  );
};

export const useNavigation = () => {
  const context = useContext(NavigationContext);
  if (context === undefined) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
};
