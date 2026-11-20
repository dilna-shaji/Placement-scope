import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useUI } from '../../context/UIContext';

/** Full-viewport shell. Sidebar and content scroll independently; <body> never scrolls. */
export function AppShell({ children }: { children: ReactNode }) {
  const { route } = useUI();
  return (
    <div className="h-screen w-screen flex overflow-hidden bg-canvas">
      <Sidebar />
      <div className="flex-1 min-w-0 min-h-0 h-screen flex flex-col">
        <TopBar />
        <main id="content" className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
          <div className="p-5 sm:p-7 lg:p-9 xl:px-10 w-full">
            <AnimatePresence mode="wait">
              <motion.div key={route} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .22 }}>
                {children}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
