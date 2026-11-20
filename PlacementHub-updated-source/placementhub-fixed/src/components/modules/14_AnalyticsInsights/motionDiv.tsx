import { motion } from 'motion/react';
export const MotionDiv = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <motion.div className={className} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-40px' }} transition={{ duration: .45 }}>{children}</motion.div>
);
