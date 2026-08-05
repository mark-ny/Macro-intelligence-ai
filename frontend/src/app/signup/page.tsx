"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { createClient } from "@/lib/supabase/client";
import { FormField } from "@/components/ui/FormField";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { data, error: signUpError } = await supabase.auth.signUp({ email, password });

    setLoading(false);
    if (signUpError) {
      setError(signUpError.message);
      return;
    }

    // With "Confirm email" off in Supabase, signUp() returns an active
    // session immediately — the account is already usable, so send them
    // straight into the app instead of showing a "check your email"
    // screen for an email that was never sent. With confirmation on,
    // no session comes back yet and the check-your-email screen below
    // is the correct state — this works either way without a code change.
    if (data.session) {
      router.push("/");
      router.refresh();
      return;
    }

    setSent(true);
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-sm">
        <h1 className="font-display text-2xl font-medium text-ink">Check your email</h1>
        <p className="mt-3 text-sm text-muted">
          We sent a confirmation link to {email}. Follow it to activate your account, then log in.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="font-display text-2xl font-medium text-ink">Sign up</h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <FormField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <FormField
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        {error && <p className="text-sm text-negative">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-gold py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="text-gold hover:underline">
          Log in
        </Link>
      </p>
    </div>
  );
}
