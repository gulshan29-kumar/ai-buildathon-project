import './globals.css';

export const metadata = {
  title: 'RazorRecover AI',
  description: 'Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
