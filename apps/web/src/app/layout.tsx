import type { Metadata } from 'next';

import { Header } from '@/components/header';

import './globals.css';

export const metadata: Metadata = {
  title: 'Tasador SD — Tasación de alquileres en Santo Domingo',
  description:
    'Estime el precio mensual de alquiler de una propiedad en Santo Domingo en segundos, con un modelo de machine learning calibrado por sector.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
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
