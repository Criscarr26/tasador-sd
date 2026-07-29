import type { Metadata } from 'next';
import { Inter, Plus_Jakarta_Sans } from 'next/font/google';
import { headers } from 'next/headers';

import { Header } from '@/components/header';

import './globals.css';

// Design system fonts (shared/design: Plus Jakarta Sans for headlines, Inter
// for body). next/font downloads and self-hosts them at build time, so no
// request ever goes to a font CDN -- those hang on TLS-inspected networks.
const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['600', '700'],
  variable: '--font-jakarta',
  display: 'swap',
});

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Tasador SD — Tasación de alquileres en Santo Domingo',
  description:
    'Estime el precio mensual de alquiler de una propiedad en Santo Domingo en segundos, con un modelo de machine learning calibrado por sector.',
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Reading the request headers opts every route into dynamic rendering,
  // which is what lets Next.js tag its inline scripts with the per-request
  // CSP nonce set in middleware. Without this the pages prerender static
  // (no nonce) and the nonce CSP would block hydration.
  await headers();
  return (
    <html lang="es" className={`${jakarta.variable} ${inter.variable}`}>
      <body>
        <Header />
        <main>{children}</main>
        <footer className="site-footer">
          <div className="container">
            Estimación orientativa, no constituye tasación oficial.
            <br />
            Versión demo entrenada con 500 registros sintéticos calibrados al mercado de
            alquileres de Santo Domingo.
          </div>
        </footer>
      </body>
    </html>
  );
}
