import './globals.css';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';

export const metadata = {
  title: 'RazorRecover AI | Autonomous Fintech Revenue Recovery',
  description: 'Enterprise Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-fintech-bg text-slate-100 min-h-screen flex flex-col antialiased selection:bg-indigo-600 selection:text-white">
        <Navbar />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-6 md:p-8">
            <div className="max-w-7xl mx-auto space-y-8">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
