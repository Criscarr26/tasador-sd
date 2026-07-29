// USD/DOP reference rate, fetched server-side.
//
// Server-side on purpose: the browser only ever talks to this app's own
// origin, so the CSP `connect-src 'self'` stays closed and no third-party
// host is exposed to the client. The upstream publishes once a day, so a
// 6-hour cache is plenty and keeps us far under any rate limit.
//
// Degrades quietly: if the upstream fails, the response says so and the UI
// simply omits the USD line rather than showing a stale or invented rate.

export const revalidate = 21600; // 6 h

const UPSTREAM = 'https://open.er-api.com/v6/latest/USD';

export async function GET() {
  try {
    const upstream = await fetch(UPSTREAM, {
      next: { revalidate },
      signal: AbortSignal.timeout(8000),
    });
    if (!upstream.ok) throw new Error(`upstream ${upstream.status}`);

    const body = await upstream.json();
    const rate = body?.rates?.DOP;

    // A rate outside this band means the feed changed shape or broke; a
    // wrong conversion is worse than no conversion.
    if (typeof rate !== 'number' || rate < 30 || rate > 150) {
      throw new Error('rate out of expected range');
    }

    return Response.json({
      ok: true,
      dopPerUsd: rate,
      updated: body?.time_last_update_utc ?? null,
      source: 'exchangerate-api.com',
    });
  } catch {
    return Response.json({ ok: false }, { status: 200 });
  }
}
