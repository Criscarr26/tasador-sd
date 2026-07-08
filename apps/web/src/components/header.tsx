'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { supabase } from '@/lib/supabase';
import { useSession } from '@/lib/use-session';

export function Header() {
  const pathname = usePathname();
  const { session } = useSession();

  return (
    <header className="site-header">
      <div className="container">
        <Link href="/" className="brand">
          <span className="brand-dot" aria-hidden />
          Tasador SD
        </Link>
        <nav className="nav" aria-label="Principal">
          <Link href="/" className={pathname === '/' ? 'active' : ''}>
            Tasador
          </Link>
          <Link href="/historial" className={pathname === '/historial' ? 'active' : ''}>
            Historial
          </Link>
        </nav>
        <div className="session-chip">
          {session ? (
            <>
              <span className="email">{session.user.email}</span>
              <button onClick={() => supabase?.auth.signOut()}>Salir</button>
            </>
          ) : (
            <Link href="/historial">Entrar</Link>
          )}
        </div>
      </div>
    </header>
  );
}
