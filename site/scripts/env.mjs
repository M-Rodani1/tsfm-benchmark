// Refuse to build with a secret Supabase key: only the public anon/publishable key may ship.
export function checkSupabaseEnv(env = process.env) {
  const problems = [];
  const key = env.VITE_SUPABASE_ANON_KEY ?? "";
  if (key.startsWith("sb_secret_")) problems.push("VITE_SUPABASE_ANON_KEY is a Supabase *secret* key; use the publishable/anon key.");
  const parts = key.split(".");
  if (parts.length === 3) {
    try {
      const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
      if (payload.role === "service_role") problems.push("VITE_SUPABASE_ANON_KEY is the service_role key; never ship it to the browser.");
    } catch {
      /* not a JWT: fine */
    }
  }
  for (const [name, value] of Object.entries(env))
    if (name.startsWith("VITE_") && /service_role|sb_secret_/i.test(String(value)) && name !== "VITE_SUPABASE_ANON_KEY")
      problems.push(`${name} looks like a secret key; VITE_* variables are public.`);
  const configured = Boolean(env.VITE_SUPABASE_URL && key);
  return { configured, problems };
}
