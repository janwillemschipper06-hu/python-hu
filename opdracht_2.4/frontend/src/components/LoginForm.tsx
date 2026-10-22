import logo from "../pictures/idNw5WxKBU_1775051280371.png";

interface LoginFormProps {
  onLogin: () => void;
  loading: boolean;
  error: string | null;
}

export function LoginForm({ onLogin, loading, error }: LoginFormProps) {
  return (
    <div className="min-h-screen bg-brand-surface flex flex-col">
      {/* Top bar — white nav matching the 9altitudes header */}
      <div className="bg-white border-b border-brand-border px-6 py-4 flex items-center">
        <img src={logo} alt="nine altitudes" className="h-8" />
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="bg-white border border-brand-border w-full max-w-sm p-8 text-center">
          <h1 className="text-2xl font-bold text-brand-dark mb-1">
            Customer Onboarding
          </h1>
          <p className="text-sm text-brand-muted mb-8">Portal</p>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 px-3 py-2 mb-5">
              {error}
            </p>
          )}

          <button
            type="button"
            onClick={onLogin}
            disabled={loading}
            className="w-full bg-brand-primary hover:bg-brand-dark text-white font-medium text-sm px-4 py-2.5 rounded transition-colors disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in with Microsoft"}
          </button>
        </div>
      </div>
    </div>
  );
}
